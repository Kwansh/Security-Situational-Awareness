"""
测试数据管道 - 项目 1 的核心测试
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import DatasetLoader
from src.data.feature_extractor import FeatureExtractor
from src.preprocess.preprocessor import Preprocessor
from src.models.trainer import ModelTrainer
from src.models.ensemble import EnsembleModel
from src.utils.evaluator import Evaluator
from src.utils.feature_selector import FeatureSelector


class TestDatasetLoader:
    """测试数据加载器"""
    
    def test_loader_initialization(self, tmp_path):
        """测试加载器初始化"""
        test_dir = tmp_path / "test_data"
        test_dir.mkdir()
        
        loader = DatasetLoader(str(test_dir))
        assert loader.data_dir == test_dir
    
    def test_load_empty_dir(self, tmp_path):
        """测试空目录"""
        test_dir = tmp_path / "empty"
        test_dir.mkdir()
        
        loader = DatasetLoader(str(test_dir))
        with pytest.raises(FileNotFoundError):
            loader.load_all()


class TestFeatureExtractor:
    """测试特征提取器"""
    
    def test_standard_mode(self):
        """测试标准特征提取"""
        df = pd.DataFrame({
            "Timestamp": pd.date_range("2024-01-01", periods=100, freq="S"),
            "Destination Port": [80] * 100,
            "Source Port": range(1000, 1100),
            "Protocol": [6] * 100,
            "SYN Flag Count": [1] * 100,
            "Packet Length Mean": [500.0] * 100,
        })
        
        extractor = FeatureExtractor(mode="standard")
        features, columns = extractor.extract(df)
        
        assert not features.empty
        assert len(columns) == 6
        assert "pkt_rate" in features.columns
    
    def test_invalid_mode(self):
        """测试无效模式"""
        with pytest.raises(ValueError):
            FeatureExtractor(mode="invalid")


class TestPreprocessor:
    """测试预处理器"""
    
    def test_clean_columns(self):
        """测试列清洗"""
        df = pd.DataFrame({
            " Column1 ": [1, 2, 3],
            "Column2": [4, 5, 6],
        })
        
        preprocessor = Preprocessor()
        cleaned = preprocessor.clean(df)
        
        assert "Column1" in cleaned.columns
        assert " Column1 " not in cleaned.columns
    
    def test_split(self):
        """测试数据分割"""
        df = pd.DataFrame({
            "feature1": [1.0, 2.0, 3.0, 4.0],
            "feature2": [5.0, 6.0, 7.0, 8.0],
            "Label": [0, 1, 0, 1],
        })
        
        preprocessor = Preprocessor(label_column="Label")
        X, y = preprocessor.split(df)
        
        assert X.shape == (4, 2)
        assert len(y) == 4


class TestModelTrainer:
    """测试模型训练器"""
    
    def test_train_simple(self):
        """测试简单训练"""
        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.randint(0, 2, 100)
        
        trainer = ModelTrainer()
        result = trainer.train_models(X, y)
        
        assert result.rf is not None
        assert hasattr(result.rf, 'predict')


class TestEnsembleModel:
    """测试集成模型"""
    
    def test_voting_ensemble(self):
        """测试 Voting 集成"""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        
        np.random.seed(42)
        X = np.random.randn(100, 5)
        y = np.random.randint(0, 2, 100)
        
        ensemble = EnsembleModel(
            {"rf": RandomForestClassifier(n_estimators=10), 
             "lr": LogisticRegression()},
            use_stacking=False
        )
        ensemble.fit(X, y)
        
        predictions = ensemble.predict(X[:10])
        assert len(predictions) == 10


class TestEvaluator:
    """测试评估器"""
    
    def test_evaluate(self):
        """测试评估"""
        from sklearn.ensemble import RandomForestClassifier
        
        np.random.seed(42)
        X = np.random.randn(100, 5)
        y = np.random.randint(0, 2, 100)
        
        model = RandomForestClassifier(n_estimators=10)
        model.fit(X, y)
        
        metrics = Evaluator.evaluate(model, X, y)
        
        assert "accuracy" in metrics
        assert 0 <= metrics["accuracy"] <= 1


class TestFeatureSelector:
    """测试特征选择器"""
    
    def test_select_k(self):
        """测试选择 K 个特征"""
        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.randint(0, 2, 100)
        
        selector = FeatureSelector(k=5)
        X_selected = selector.fit_transform(X, y)
        
        assert X_selected.shape[1] <= 5


class TestIntegration:
    """集成测试"""
    
    def test_full_pipeline(self, tmp_path):
        """测试完整流程"""
        # 创建测试数据
        test_dir = tmp_path / "data"
        test_dir.mkdir()
        
        df = pd.DataFrame({
            "Timestamp": pd.date_range("2024-01-01", periods=200, freq="S"),
            "Destination Port": [80] * 200,
            "Source Port": range(1000, 1200),
            "Protocol": [6] * 200,
            "SYN Flag Count": [1] * 200,
            "Packet Length Mean": [500.0] * 200,
            "Label": [0] * 100 + [1] * 100,
        })
        
        csv_path = test_dir / "test.csv"
        df.to_csv(csv_path, index=False)
        
        # 1. 加载数据
        loader = DatasetLoader(str(test_dir))
        loaded_df = loader.load_all()
        assert len(loaded_df) > 0
        
        # 2. 提取特征
        extractor = FeatureExtractor(mode="standard")
        features, columns = extractor.fit_extract(loaded_df)
        assert not features.empty
        
        # 3. 预处理
        preprocessor = Preprocessor(label_column="Label")
        X, y = preprocessor.split(loaded_df)
        X_norm = preprocessor.normalize(X.values, fit=True)
        
        # 4. 训练
        trainer = ModelTrainer()
        trainer.train_models(X_norm, y.values)
        
        assert trainer.rf is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
