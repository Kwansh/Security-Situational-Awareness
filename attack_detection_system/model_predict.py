import joblib
import pandas as pd

def load_models():
    clf = joblib.load("models/attack_model.pkl")
    iso = joblib.load("models/anomaly_model.pkl")
    scaler = joblib.load("models/scaler.pkl")
    return clf, iso, scaler

def predict(data_path):
    df = pd.read_csv(data_path)
    clf, iso, scaler = load_models()
    X = df.drop(["label"], axis=1)
    X_scaled = scaler.transform(X)
    df["ml_prediction"] = clf.predict(X_scaled)
    df["anomaly_score"] = iso.predict(X_scaled)   # 1正常，-1异常
    return df