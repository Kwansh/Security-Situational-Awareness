# 杩愯鎸囧崡 - 椤圭洰 2 鐨勫畬鏁存枃妗?
## 鍦?VSCode 涓繍琛岄」鐩?
---

## 鏂规硶涓€锛氫娇鐢?VSCode 缁堢锛堟帹鑽愶級猸?
### 姝ラ 1锛氭墦寮€缁堢

鍦?VSCode 涓紝鎸?`` Ctrl + ` ``锛堝弽寮曞彿锛夋垨鐐瑰嚮鑿滃崟 **缁堢 鈫?鏂板缓缁堢**

### 姝ラ 2锛氬畨瑁呬緷璧?
鍦ㄧ粓绔腑杈撳叆锛?
```bash
# 杩涘叆椤圭洰鐩綍锛堝鏋滆繕娌″湪椤圭洰涓級
cd security-situational-awareness-ultimate

# 瀹夎 Python 渚濊禆鍖?pip install -r requirements.txt
```

**绛夊緟瀹夎瀹屾垚**锛岀湅鍒?`Successfully installed` 琛ㄧず鎴愬姛銆?
### 姝ラ 3锛氳缁冩ā鍨?
```bash
# 璁粌鍩虹妯″瀷
python scripts/train.py --data_dir data/raw --output_dir data/models

# 鎴栬缁冮泦鎴愭ā鍨嬶紙鎺ㄨ崘锛?python scripts/train_advanced.py --input data/raw --models auto --use-stacking

# 在线学习更新
python scripts/train_online.py --data_dir data/raw --artifact_path data/models/model_artifacts.pkl
```

### 姝ラ 4锛氬惎鍔?API 鏈嶅姟

```bash
python run_api.py --host 0.0.0.0 --port 8000
```

### 姝ラ 5锛氳闂?API 鏂囨。

鎵撳紑娴忚鍣ㄨ闂細http://localhost:8000/docs

---

## 鏂规硶浜岋細浣跨敤 VSCode 杩愯鎸夐挳

### 姝ラ 1锛氭墦寮€涓荤▼搴忔枃浠?
鍦?VSCode 宸︿晶鏂囦欢娴忚鍣ㄤ腑锛屾壘鍒板苟鎵撳紑锛?```
run_api.py
```

### 姝ラ 2锛氱偣鍑诲彸涓婅杩愯鎸夐挳

VSCode 鍙充笂瑙掍細鍑虹幇 **鈻讹笍 杩愯** 鎸夐挳锛岀偣鍑诲嵆鍙繍琛屻€?
### 姝ラ 3锛氭煡鐪嬭緭鍑?
绋嬪簭杈撳嚭浼氭樉绀哄湪 **缁堢** 闈㈡澘涓€?
---

## 鏂规硶涓夛細浣跨敤 Python 璋冭瘯鍣?
### 姝ラ 1锛氬垱寤哄惎鍔ㄩ厤缃?
1. 鎸?`F5` 鎴栫偣鍑?**杩愯鍜岃皟璇?* 鍥炬爣
2. 閫夋嫨 **鍒涘缓 launch.json 鏂囦欢**
3. 閫夋嫨 **Python 鏂囦欢**

### 姝ラ 2锛氫慨鏀归厤缃?
灏嗙敓鎴愮殑 `launch.json` 淇敼涓猴細

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "杩愯 API 鏈嶅姟",
            "type": "debugpy",
            "request": "launch",
            "module": "uvicorn",
            "args": ["src.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}"
        },
        {
            "name": "璁粌妯″瀷",
            "type": "debugpy",
            "request": "launch",
            "module": "scripts.train",
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}"
        }
    ]
}
```

### 姝ラ 3锛氬惎鍔ㄨ皟璇?
鎸?`F5` 鍚姩锛屽彲浠ユ柇鐐硅皟璇曘€?
---

## 馃搵 甯哥敤鍛戒护閫熸煡

| 鍔熻兘 | 鍛戒护 |
|------|------|
| **瀹夎渚濊禆** | `pip install -r requirements.txt` |
| **璁粌妯″瀷** | `python scripts/train.py --data_dir data/raw --test_size 0.2` |
| **楂樼骇璁粌** | `python scripts/train_advanced.py --input data/raw --models auto --use-stacking` |
| **在线学习** | `python scripts/train_online.py --data_dir data/raw --artifact_path data/models/model_artifacts.pkl` |
| **鎻愬彇鐗瑰緛** | `python scripts/extract_features.py --input data/raw` |
| **鎵归噺棰勬祴** | `python scripts/predict.py --input test.csv --output results/predictions.csv` |
| **鍚姩 API** | `python run_api.py --host 0.0.0.0 --port 8000` |
| **模型热重载** | `POST /admin/reload-model` |
| **杩愯娴嬭瘯** | `pytest tests/ -v` |
| **鏇挎崲妯″瀷** | `python scripts/swap_model.py --new-model model.pkl` |

---

## 鈿狅笍 甯歌闂瑙ｅ喅

### 闂 1锛歚pip: command not found`

**Windows 瑙ｅ喅鏂规锛?*
```bash
# 浣跨敤 python -m pip
python -m pip install -r requirements.txt
```

### 闂 2锛歚ModuleNotFoundError: No module named 'xxx'`

**鍘熷洜锛?* 渚濊禆鍖呮湭瀹夎

**瑙ｅ喅锛?*
```bash
pip install pandas numpy scikit-learn joblib matplotlib seaborn pyyaml fastapi uvicorn
```

### 闂 3锛氭潈闄愰敊璇?`Permission denied`

**Linux/Mac 瑙ｅ喅鏂规锛?*
```bash
# 浣跨敤 --user 鍙傛暟
pip install --user -r requirements.txt
```

### 闂 4锛氫腑鏂囦贡鐮?
**瑙ｅ喅锛?* 鍦?VSCode 璁剧疆涓慨鏀圭紪鐮?1. 鎸?`Ctrl + Shift + P`
2. 杈撳叆 `Change File Encoding`
3. 閫夋嫨 `UTF-8 with BOM`

---

## 馃幆 鎺ㄨ崘杩愯椤哄簭

**绗竴娆¤繍琛岋細**

```bash
# 1. 瀹夎渚濊禆
pip install -r requirements.txt

# 2. 鍑嗗鏁版嵁
mkdir -p data/raw
# 鏀惧叆浣犵殑 CSV 鏂囦欢

# 3. 璁粌妯″瀷
python scripts/train.py --data_dir data/raw --test_size 0.2

# 4. 鍚姩 API
python run_api.py --host 0.0.0.0 --port 8000

# 5. 璁块棶 http://localhost:8000/docs
```

**鍚庣画寮€鍙戯細**

```bash
# 1. 鐢熸垚鑷繁鐨勬暟鎹紙鍙€夛級
python scripts/extract_features.py --input data/raw

# 2. 璁粌鏂版ā鍨嬶紙鍙€夛級
python scripts/train_advanced.py --input data/raw --models auto --use-stacking

# 3. 杩愯妫€娴?python run_api.py --host 0.0.0.0 --port 8000
```

---

## 馃搳 棰勬湡杈撳嚭绀轰緥

### 璁粌妯″瀷杈撳嚭

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

============================================================
馃搳 璁粌鎶ュ憡
============================================================
鏈€浣虫ā鍨嬶細random_forest

璇勪及鎸囨爣:
  accuracy: 0.9950
  precision: 0.9948
  recall: 0.9950
  f1_score: 0.9948

鉁?璁粌瀹屾垚!
============================================================
```

### API 鍚姩杈撳嚭

```
============================================================
缃戠粶瀹夊叏鎬佸娍鎰熺煡绯荤粺 - API 鏈嶅姟
============================================================

馃殌 鍚姩 API 鏈嶅姟...

璁块棶浠ヤ笅鍦板潃:
  - API 鏂囨。锛歨ttp://localhost:8000/docs
  - 鍋ュ悍妫€鏌ワ細http://localhost:8000/health
  - 鍏冩暟鎹細http://localhost:8000/metadata

鎸?Ctrl+C 鍋滄鏈嶅姟
============================================================
```

---

## 馃挕 杩涢樁浣跨敤

### 浣跨敤鑷繁鐨勬暟鎹?
1. 鍑嗗 CSV 鏂囦欢锛屽寘鍚互涓嬪垪锛?   - Timestamp
   - Destination Port
   - Source Port
   - Protocol
   - SYN Flag Count
   - Packet Length Mean
   - Label

2. 灏嗘枃浠舵斁鍏?`data/raw/` 鐩綍

3. 杩愯锛?```bash
python scripts/train.py --data_dir data/raw --test_size 0.2
```

### 淇敼妫€娴嬮槇鍊?
缂栬緫 `config/config.yaml`锛?
```yaml
rule_thresholds:
  syn_flood_per_sec: 500    # 璋冮珮/闄嶄綆 SYN 妫€娴嬮槇鍊?  udp_flood_per_min: 10000  # 璋冮珮/闄嶄綆 UDP 妫€娴嬮槇鍊?  dns_flood_per_sec: 2000   # 璋冮珮/闄嶄綆 DNS 妫€娴嬮槇鍊?```

---

## 馃摓 闇€瑕佸府鍔╋紵

濡傛灉閬囧埌鍏朵粬闂锛?
1. 鏌ョ湅鏃ュ織鏂囦欢
2. 妫€鏌?Python 鐗堟湰锛歚python --version`锛堥渶瑕?3.10+锛?3. 鏌ョ湅椤圭洰鏂囨。锛歚README.md`

**绁濅綘浣跨敤鎰夊揩锛?* 馃帀


