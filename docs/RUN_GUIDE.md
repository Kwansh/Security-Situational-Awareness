# 杩愯鎸囧崡

## 蹇€熷紑濮?
### 1. 瀹夎渚濊禆
```bash
pip install -r requirements.txt
```

### 2. 璁粌妯″瀷
```bash
python scripts/train.py --data_dir data/raw --test_size 0.2
```

### 3. 鍚姩 API
```bash
python run_api.py --host 0.0.0.0 --port 8000
```

### 4. 在线学习更新
```bash
python scripts/train_online.py --data_dir data/raw --artifact_path data/models/model_artifacts.pkl
```

### 5. 璁块棶鏂囨。
http://localhost:8000/docs

## 甯哥敤鍛戒护

| 鍔熻兘 | 鍛戒护 |
|------|------|
| 瀹夎渚濊禆 | `pip install -r requirements.txt` |
| 璁粌妯″瀷 | `python scripts/train.py --data_dir data/raw --test_size 0.2` |
| 鎻愬彇鐗瑰緛 | `python scripts/extract_features.py --input data/raw` |
| 鎵归噺棰勬祴 | `python scripts/predict.py --input test.csv` |
| 鍚姩 API | `python run_api.py --host 0.0.0.0 --port 8000` |
| 杩愯娴嬭瘯 | `pytest tests/ -v` |
| 鏇挎崲妯″瀷 | `python scripts/swap_model.py --new-model model.pkl` |

## 棰勬湡杈撳嚭

```
============================================================
缃戠粶瀹夊叏鎬佸娍鎰熺煡绯荤粺 - 妯″瀷璁粌
============================================================

馃搨 鍔犺浇鏁版嵁 from data/raw...
鉁?鍔犺浇瀹屾垚锛?000 琛屾暟鎹?
馃敡 鎻愬彇鐗瑰緛 (mode=hybrid)...
鉁?鐗瑰緛鎻愬彇瀹屾垚锛?1000, 36) 褰㈢姸

馃Ч 鏁版嵁棰勫鐞?..
鉁?棰勫鐞嗗畬鎴愶細(1000, 36) 褰㈢姸

馃 璁粌妯″瀷...
Training random_forest...
  Accuracy: 0.9950
  F1-Score: 0.9948

馃捑 淇濆瓨妯″瀷鍒?data/models/model_artifacts.pkl...

鉁?璁粌瀹屾垚!
============================================================
```

