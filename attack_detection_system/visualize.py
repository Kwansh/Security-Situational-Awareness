import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import os

def plot_attack_type_distribution(df, save_path):
    """攻击类型分布饼图/条形图"""
    plt.figure(figsize=(8, 5))
    # 统计规则检测到的攻击类型
    attack_counts = df[df["rule_attack_type"] != "NORMAL"]["rule_attack_type"].value_counts()
    if not attack_counts.empty:
        attack_counts.plot(kind="bar", color="skyblue", edgecolor="black")
        plt.title("攻击类型分布")
        plt.xlabel("攻击类型")
        plt.ylabel("数量")
        plt.tight_layout()
        plt.savefig(os.path.join(save_path, "attack_type_dist.png"))
        plt.close()
    else:
        print("未检测到攻击，不生成攻击类型分布图")

def plot_top_attack_ips(df, save_path, ip_col="src_ip"):
    """攻击源IP排行榜（假设数据中有src_ip列）"""
    if ip_col not in df.columns:
        print(f"数据中无{ip_col}列，跳过IP排行图")
        return
    attack_ips = df[df["rule_attack_type"] != "NORMAL"][ip_col].value_counts().head(10)
    if not attack_ips.empty:
        plt.figure(figsize=(10, 6))
        sns.barplot(x=attack_ips.values, y=attack_ips.index, palette="Reds_r")
        plt.title("Top 10 攻击源IP")
        plt.xlabel("攻击次数")
        plt.tight_layout()
        plt.savefig(os.path.join(save_path, "top_attack_ips.png"))
        plt.close()
    else:
        print("无攻击IP数据，跳过IP排行图")

def plot_time_trend(df, save_path, time_col="timestamp"):
    """攻击随时间变化趋势（需要时间戳列）"""
    if time_col not in df.columns:
        print(f"数据中无{time_col}列，跳过时间趋势图")
        return
    # 假设时间戳已排序，计算每分钟攻击次数
    df[time_col] = pd.to_datetime(df[time_col])
    df.set_index(time_col, inplace=True)
    attack_series = (df["rule_attack_type"] != "NORMAL").resample("1T").sum()
    plt.figure(figsize=(12, 5))
    plt.plot(attack_series.index, attack_series.values, marker='o', linestyle='-', color='red')
    plt.title("攻击时间趋势（每分钟攻击数）")
    plt.xlabel("时间")
    plt.ylabel("攻击次数")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(save_path, "time_trend.png"))
    plt.close()
    # 恢复索引
    df.reset_index(inplace=True)

def generate_all_visualizations(df, save_dir="results/figures"):
    """生成所有可视化图表"""
    os.makedirs(save_dir, exist_ok=True)
    plot_attack_type_distribution(df, save_dir)
    plot_top_attack_ips(df, save_dir)
    plot_time_trend(df, save_dir)
    print("可视化图表已生成至", save_dir)