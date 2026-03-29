import pandas as pd
from rule_engine import RuleEngine
from model_predict import predict
from attack_explainer import AttackExplainer
from visualize import generate_all_visualizations
from evaluation import evaluate

def main():
    print("========== 攻击检测系统启动 ==========")

    # 1. 加载数据
    data_path = "data/test.csv"
    df = pd.read_csv(data_path)
    print(f"数据加载完成，共 {len(df)} 条记录")

    # 2. 规则检测
    rule_engine = RuleEngine()
    df = rule_engine.run_rules(df)
    print("规则检测完成")

    # 3. 机器学习检测
    df_ml = predict(data_path)
    df["ml_prediction"] = df_ml["ml_prediction"]
    df["anomaly_score"] = df_ml["anomaly_score"]
    print("机器学习检测完成")

    # 4. 攻击解释
    explainer = AttackExplainer()
    df = explainer.generate_explanation(df)
    print("攻击解释生成完成")

    # 5. 保存详细结果
    df.to_csv("results/attack_results.csv", index=False)
    print("检测结果已保存至 results/attack_results.csv")

    # 6. 可视化
    generate_all_visualizations(df, save_dir="results/figures")

    # 7. 评估（基于机器学习预测）
    evaluate(df["label"], df["ml_prediction"])

    print("========== 系统运行完毕 ==========")

if __name__ == "__main__":
    main()