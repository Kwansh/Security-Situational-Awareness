import pandas as pd

class DummyPreprocessor:
    """
    解耦后的预处理器类。
    职责：清理 CSV 中的标签列，确保输入 Scaler 的特征列对齐。
    """
    def transform_dataframe(self, df, fit=False):
        # 排除掉评估脚本中可能出现的所有标签列名
        exclude = ["Label", "label", "Class", "class", "Target", "target", "y", "Y"]
        cols = [c for c in df.columns if c not in exclude]
        # 返回只包含特征数据的 DataFrame，确保后续 Scaler 不会报错
        return df[cols]