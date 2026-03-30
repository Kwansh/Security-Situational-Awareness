import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.model_artifacts import DEFAULT_ARTIFACT_NAME, load_artifacts
from src.preprocess import Preprocessor

artifacts = None


class PredictionRequest(BaseModel):
    features: list[float]


def get_artifact_path() -> Path:
    return Path(os.getenv("MODEL_ARTIFACT_PATH", f"data/models/{DEFAULT_ARTIFACT_NAME}"))


def reverse_label_mapping():
    if not artifacts:
        return {}
    mapping = artifacts.get("label_mapping") or {}
    return {value: key for key, value in mapping.items()}


def predict_array(feature_array: np.ndarray):
    if artifacts is None:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")

    expected_features = len(artifacts["feature_columns"])
    if feature_array.shape[1] != expected_features:
        raise HTTPException(
            status_code=422,
            detail=f"Expected {expected_features} features, got {feature_array.shape[1]}.",
        )

    scaled = artifacts["scaler"].transform(feature_array)
    selected = artifacts["selector"].transform(scaled)
    prediction = artifacts["model"].predict(selected)
    probabilities = artifacts["model"].predict_proba(selected)[0]
    confidence = float(np.max(probabilities))
    label = reverse_label_mapping().get(int(prediction[0]), str(int(prediction[0])))

    return {
        "prediction": int(prediction[0]),
        "prediction_label": label,
        "confidence": confidence,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def load_models():
    global artifacts
    artifact_path = get_artifact_path()
    if artifact_path.exists():
        artifacts = load_artifacts(artifact_path)
    else:
        artifacts = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_models()
    yield


app = FastAPI(title="DDoS Detection API", version="2.0", lifespan=lifespan)


@app.get("/health")
def health():
    feature_count = len(artifacts["feature_columns"]) if artifacts else 0
    return {
        "status": "ok" if artifacts else "missing_model",
        "model_loaded": artifacts is not None,
        "artifact_path": str(get_artifact_path()),
        "feature_count": feature_count,
    }


@app.get("/metadata")
def metadata():
    if artifacts is None:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")
    return {
        "feature_columns": artifacts["feature_columns"],
        "label_mapping": artifacts.get("label_mapping", {}),
        "metrics": {key: value for key, value in artifacts.get("metrics", {}).items() if key != "report"},
    }


@app.post("/predict")
def predict(request: PredictionRequest):
    feature_array = np.asarray(request.features, dtype=float).reshape(1, -1)
    return predict_array(feature_array)


@app.post("/predict/batch")
async def predict_batch(file: UploadFile = File(...)):
    if artifacts is None:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded.")

    content = await file.read()
    df = pd.read_csv(pd.io.common.BytesIO(content), low_memory=False)
    preprocessor = Preprocessor()
    df = preprocessor.clean(df)

    missing_columns = sorted(set(artifacts["feature_columns"]) - set(df.columns))
    if missing_columns:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required feature columns: {missing_columns[:10]}",
        )

    feature_frame = df[artifacts["feature_columns"]].copy()
    for column in feature_frame.columns:
        feature_frame[column] = pd.to_numeric(feature_frame[column], errors="coerce")
    feature_frame = feature_frame.fillna(feature_frame.median(numeric_only=True)).fillna(0.0)

    scaled = artifacts["scaler"].transform(feature_frame.values)
    selected = artifacts["selector"].transform(scaled)
    predictions = artifacts["model"].predict(selected)
    probabilities = artifacts["model"].predict_proba(selected).max(axis=1)
    label_map = reverse_label_mapping()

    results = []
    for index, (prediction, confidence) in enumerate(zip(predictions, probabilities)):
        results.append(
            {
                "index": index,
                "prediction": int(prediction),
                "prediction_label": label_map.get(int(prediction), str(int(prediction))),
                "confidence": float(confidence),
            }
        )

    return {"total": len(results), "predictions": results}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            features = payload.get("features")
            if features is None:
                await websocket.send_json({"error": "Missing features"})
                continue
            try:
                feature_array = np.asarray(features, dtype=float).reshape(1, -1)
                await websocket.send_json(predict_array(feature_array))
            except HTTPException as exc:
                await websocket.send_json({"error": exc.detail})
    except WebSocketDisconnect:
        return
