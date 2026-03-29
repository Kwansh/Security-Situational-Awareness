# ==============================
# 成员B：特征提取 + 输出PKL给C
# 【100%适配你提供的CICFlowMeter CSV表头】
# 输出：train_features.pkl
# ==============================

import pandas as pd
import numpy as np
import os
import glob
import joblib

# ====================== 接口规范固定 ======================
FEATURE_NAMES = [
    "pkt_rate",
    "syn_rate",
    "udp_rate",
    "dns_rate",
    "ntp_rate",
    "avg_pkt_size"
]

WINDOW_SEC = 1
LABEL_MAPPING = {
    "normal": 0,
    "syn_flood": 1,
    "udp_flood": 2,
    "udplag_flood": 3,
    "ldap_flood": 4,
    "mssql_flood": 5,
    "netbios_flood": 6,
    "portmap_flood": 7,
    "dns_flood": 8,
    "ntp_flood": 9
}

# ====================== 你的真实路径 ======================
INPUT_CSV_FOLDER = "C:/Users/susu/Desktop/大创/CSV-03-11"
OUTPUT_PKL_PATH = "C:/Users/susu/Desktop/train_features.pkl"

# ====================== 核心：适配你的CSV列名 ======================
def extract_features_from_df(df, attack_label="normal"):
    # 【关键】清洗列名：去掉前后空格 → 适配你的表头
    df.columns = df.columns.str.strip()
    
    # 你的CSV里必须有的列（已核对你给的表头）
    required = ["Timestamp", "Destination Port", "Source Port", "Protocol", "SYN Flag Count", "Label"]
    for col in required:
        if col not in df.columns:
            print(f"⚠️  缺少列: {col}，跳过")
            return np.empty((0,6)), np.array([])

    # 时间处理
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df.dropna(subset=["Timestamp"]).copy()
    if len(df) == 0:
        return np.empty((0,6)), np.array([])

    df["window"] = df["Timestamp"].dt.floor("1S")
    windows = df["window"].unique()
    if len(windows) == 0:
        return np.empty((0,6)), np.array([])

    # -------------------- 6个标准特征（严格按接口） --------------------
    # 1. 每秒包数
    pkt_rate = df.groupby("window").size().reindex(windows, fill_value=0).values

    # 2. SYN速率 (Protocol=6, SYN Flag=1)
    syn_mask = (df["Protocol"] == 6) & (df["SYN Flag Count"] == 1)
    syn_rate = df[syn_mask].groupby("window").size().reindex(windows, fill_value=0).values

    # 3. UDP速率 (Protocol=17)
    udp_mask = df["Protocol"] == 17
    udp_rate = df[udp_mask].groupby("window").size().reindex(windows, fill_value=0).values

    # 4. DNS (53端口)
    dns_mask = (df["Destination Port"] == 53) | (df["Source Port"] == 53)
    dns_rate = df[dns_mask].groupby("window").size().reindex(windows, fill_value=0).values

    # 5. NTP (123端口)
    ntp_mask = (df["Destination Port"] == 123) | (df["Source Port"] == 123)
    ntp_rate = df[ntp_mask].groupby("window").size().reindex(windows, fill_value=0).values

    # 6. 平均包大小（用你的列：Packet Length Mean）
    avg_pkt_size = df.groupby("window")["Packet Length Mean"].mean().reindex(windows, fill_value=0).values

    # 拼接
    X = np.column_stack([pkt_rate, syn_rate, udp_rate, dns_rate, ntp_rate, avg_pkt_size])
    y = np.array([attack_label] * len(X))
    return X, y

# ====================== 批量构建数据集 ======================
def build_dataset():
    csv_files = glob.glob(os.path.join(INPUT_CSV_FOLDER, "*.csv"))
    print(f"📂 找到 {len(csv_files)} 个CSV文件")

    X_list, y_list = [], []
    for f in csv_files:
        fname = os.path.basename(f).lower()
        print(f"\n正在处理：{fname}")

        # 自动匹配攻击类型
        if "syn" in fname:
            label = "syn_flood"
        elif "udplag" in fname:
            label = "udplag_flood"
        elif "udp" in fname:
            label = "udp_flood"
        elif "ldap" in fname:
            label = "ldap_flood"
        elif "mssql" in fname:
            label = "mssql_flood"
        elif "netbios" in fname:
            label = "netbios_flood"
        elif "portmap" in fname:
            label = "portmap_flood"
        else:
            label = "normal"

        # 只读取前5万行，防止内存爆炸
        df = pd.read_csv(f, low_memory=False, nrows=50000)
        X, y = extract_features_from_df(df, label)

        if len(X) > 0:
            X_list.append(X)
            y_list.append(y)
            print(f"✅ 提取 {len(X):>4} 条窗口特征 | 标签：{label}")
        else:
            print(f"❌ 无有效特征")

    if not X_list:
        print("\n❌ 无有效特征，生成空PKL")
        return np.empty((0,6)), np.array([])

    return np.concatenate(X_list, axis=0), np.concatenate(y_list, axis=0)

# ====================== 主程序 ======================
if __name__ == "__main__":
    print("===== 成员B：生成标准6维特征PKL =====")
    X, y = build_dataset()

    # 保存成PKL（给C成员）
    joblib.dump({
        "X": X,
        "y": y,
        "feature_names": FEATURE_NAMES,
        "label_mapping": LABEL_MAPPING,
        "window_seconds": 1
    }, OUTPUT_PKL_PATH)

    print(f"\n🎉 成功！文件已保存到：{OUTPUT_PKL_PATH}")
    print(f"📊 最终特征形状：{X.shape}")
    print(f"🏷 标签分布：")
    if len(y) > 0:
        print(pd.Series(y).value_counts())

# ==============================
# 成员C：训练模型 → 生成 ddos_model.pkl
# ==============================
import joblib
from sklearn.ensemble import RandomForestClassifier

# ✅ 绝对正确的路径
PKL_PATH = "C:/Users/susu/Desktop/train_features.pkl"
MODEL_SAVE_PATH = "C:/Users/susu/Desktop/ddos_model.pkl"

# 加载B生成的特征
data = joblib.load(PKL_PATH)
X = data["X"]
y = data["y"]

# 训练
model = RandomForestClassifier(n_estimators=50, random_state=42)
model.fit(X, y)

# 保存最终模型（给D用）
joblib.dump({
    "model": model,
    "feature_names": data["feature_names"],
    "label_mapping": data["label_mapping"]
}, MODEL_SAVE_PATH)

print("✅ 模型训练完成！ddos_model.pkl 已保存到桌面")