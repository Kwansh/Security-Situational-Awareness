import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import IsolationForest

def train_models(train_path):
    df = pd.read_csv(train_path)
    X = df.drop(["label"], axis=1)
    y = df["label"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_train, y_train)
    joblib.dump(clf, "models/attack_model.pkl")

    iso = IsolationForest(contamination=0.05)
    iso.fit(X_train)
    joblib.dump(iso, "models/anomaly_model.pkl")

    joblib.dump(scaler, "models/scaler.pkl")
    print("模型训练完成")