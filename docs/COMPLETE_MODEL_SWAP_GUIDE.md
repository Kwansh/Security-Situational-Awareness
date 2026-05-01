# 妯″瀷鏇挎崲瀹屾暣鎸囧崡 - 椤圭洰 2 鐨勫畬鏁存枃妗?
## 濡備綍灏?ddos_detect_model.pkl 鏇挎崲鍒伴」鐩腑

---

## 馃摝 鍓嶆彁鏉′欢

浣犳湁涓€涓柊鐨勬ā鍨嬫枃浠讹細**ddos_detect_model.pkl**

---

## 馃殌 涓夌鏇挎崲鏂规硶锛堜换閫夊叾涓€锛?
### 鏂规硶 1锛氫娇鐢ㄨ嚜鍔ㄨ剼鏈紙鏈€绠€鍗曪級猸愨瓙猸?
#### 姝ラ锛?
1. **涓婁紶鏂版ā鍨嬫枃浠?*
   - 灏?`ddos_detect_model.pkl` 鏀惧埌椤圭洰鏍圭洰褰?
2. **杩愯鑷姩鏇挎崲鑴氭湰**
   ```bash
   python scripts/swap_model.py
   ```

3. **楠岃瘉缁撴灉**
   - 鐪嬪埌 `鉁?妯″瀷鏇挎崲瀹屾垚锛乣 琛ㄧず鎴愬姛

4. **娴嬭瘯绯荤粺**
   ```bash
   python run_api.py --host 0.0.0.0 --port 8000
   ```

**瀹屾垚锛?* 馃帀

---

### 鏂规硶 2锛氭墜鍔ㄦ搷浣滐紙鏈€鐩磋锛夆瓙猸?
#### 姝ラ锛?
1. **涓婁紶鏂版ā鍨?*
   - 灏?`ddos_detect_model.pkl` 鏀惧埌椤圭洰鏍圭洰褰?
2. **澶囦唤鏃фā鍨?*
   - 鎵惧埌 `data/models/model_artifacts.pkl`
   - 澶嶅埗涓?`data/models/model_artifacts_backup.pkl`

3. **閲嶅懡鍚嶆柊妯″瀷**
   - 灏?`ddos_detect_model.pkl` 閲嶅懡鍚嶄负 `model_artifacts.pkl`
   - 鏀惧叆 `data/models/` 鐩綍

4. **楠岃瘉**
   ```bash
   python3 -c "import joblib; model = joblib.load('data/models/model_artifacts.pkl'); print('鉁?鎴愬姛锛?)"
   ```

---

### 鏂规硶 3锛氫娇鐢ㄥ懡浠よ锛堟渶涓撲笟锛夆瓙

#### Windows 绯荤粺锛?
```bash
# 1. 鎵撳紑缁堢

# 2. 杩涘叆椤圭洰鐩綍
cd security-situational-awareness-ultimate

# 3. 澶囦唤鏃фā鍨?copy data\models\model_artifacts.pkl data\models\model_artifacts_backup.pkl

# 4. 澶嶅埗鏂版ā鍨?copy ddos_detect_model.pkl data\models\model_artifacts.pkl

# 5. 楠岃瘉
python -c "import joblib; model = joblib.load('data\models\model_artifacts.pkl'); print('鉁?鎴愬姛锛?)"
```

#### Mac/Linux 绯荤粺锛?
```bash
# 1. 杩涘叆椤圭洰鐩綍
cd security-situational-awareness-ultimate

# 2. 澶囦唤鏃фā鍨?cp data/models/model_artifacts.pkl data/models/model_artifacts_backup.pkl

# 3. 澶嶅埗鏂版ā鍨?cp ddos_detect_model.pkl data/models/model_artifacts.pkl

# 4. 楠岃瘉
python3 -c "import joblib; model = joblib.load('data/models/model_artifacts.pkl'); print('鉁?鎴愬姛锛?)"
```

---

## 鉁?楠岃瘉妯″瀷鏄惁鍙敤

### 娴嬭瘯鑴氭湰 1锛氬熀纭€鍔犺浇娴嬭瘯

```bash
python3 -c "
import joblib

# 鍔犺浇妯″瀷
model_data = joblib.load('data/models/model_artifacts.pkl')
print('鉁?妯″瀷鍔犺浇鎴愬姛锛?)

# 妫€鏌ユā鍨嬬被鍨?print(f'妯″瀷绫诲瀷锛歿type(model_data)}')

# 濡傛灉妯″瀷鏄瓧鍏革紝鏄剧ず閿?if isinstance(model_data, dict):
    print(f'妯″瀷鍖呭惈鐨勯敭锛歿list(model_data.keys())}')
"
```

### 娴嬭瘯鑴氭湰 2锛氬畬鏁村姛鑳芥祴璇?
鍒涘缓 `test_model.py`锛?
```python
import joblib
import numpy as np

print("=" * 50)
print("妯″瀷楠岃瘉娴嬭瘯")
print("=" * 50)

# 1. 鍔犺浇妯″瀷
try:
    model_data = joblib.load('data/models/model_artifacts.pkl')
    print("鉁?姝ラ 1: 妯″瀷鍔犺浇鎴愬姛")
except Exception as e:
    print(f"鉂?姝ラ 1: 妯″瀷鍔犺浇澶辫触 - {e}")
    exit()

# 2. 妫€鏌ユā鍨嬬粨鏋?print("\n妯″瀷淇℃伅:")
if isinstance(model_data, dict):
    for key in model_data.keys():
        print(f"  - {key}: {type(model_data[key])}")
    
    # 灏濊瘯鑾峰彇妯″瀷
    if 'model' in model_data:
        model = model_data['model']
        print(f"\n鉁?鎵惧埌妯″瀷瀵硅薄锛歿type(model)}")
    
    if 'feature_columns' in model_data:
        print(f"鉁?鐗瑰緛鏁伴噺锛歿len(model_data['feature_columns'])}")
    
    if 'label_mapping' in model_data:
        print(f"鉁?鏍囩鏄犲皠锛歿model_data['label_mapping']}")
else:
    print(f"妯″瀷绫诲瀷锛歿type(model_data)}")
    model = model_data

# 3. 娴嬭瘯棰勬祴鍔熻兘
print("\n娴嬭瘯棰勬祴鍔熻兘...")
try:
    # 鍒涘缓娴嬭瘯鏁版嵁
    test_data = np.random.rand(1, len(model_data.get('feature_columns', [0]*10)))
    
    if isinstance(model_data, dict) and 'model' in model_data:
        prediction = model_data['model'].predict(test_data)
        print(f"鉁?棰勬祴缁撴灉锛歿prediction}")
    else:
        prediction = model.predict(test_data)
        print(f"鉁?棰勬祴缁撴灉锛歿prediction}")
    
except Exception as e:
    print(f"鈿狅笍 棰勬祴娴嬭瘯璺宠繃 - {e}")

print("\n" + "=" * 50)
print("鉁?妯″瀷楠岃瘉瀹屾垚锛?)
print("=" * 50)
```

杩愯娴嬭瘯锛?```bash
python test_model.py
```

---

## 馃敡 濡傛灉妯″瀷涓嶅吋瀹规€庝箞鍔烇紵

### 鎯呭喌 1锛氱壒寰佺淮搴︿笉鍖归厤

**閿欒淇℃伅**: `ValueError: X has 7 features, but model is expecting 6 features`

**瑙ｅ喅鏂规**: 妫€鏌ヤ綘鐨勬ā鍨嬭缁冩椂浣跨敤鐨勭壒寰佺淮搴︺€?
```python
# 鏌ョ湅妯″瀷鏈熸湜鐨勭壒寰佹暟
import joblib
model_data = joblib.load('data/models/model_artifacts.pkl')

if 'feature_columns' in model_data:
    print(f"鐗瑰緛鏁伴噺锛歿len(model_data['feature_columns'])}")
    print(f"鐗瑰緛鍚嶇О锛歿model_data['feature_columns']}")
```

### 鎯呭喌 2锛氭爣绛炬槧灏勪笉鍚?
**瑙ｅ喅鏂规**: 浣跨敤璁粌鏃剁殑鏍囩鏄犲皠銆?
### 鎯呭喌 3锛氭ā鍨嬫牸寮忓畬鍏ㄤ笉鍚?
濡傛灉浣犵殑妯″瀷鏄敤涓嶅悓鏂瑰紡璁粌鐨勶紝闇€瑕佷慨鏀瑰姞杞戒唬鐮併€?
---

## 馃搳 鏇挎崲鍚庢祴璇曞畬鏁寸郴缁?
### 姝ラ 1锛氬惎鍔?API

```bash
python run_api.py --host 0.0.0.0 --port 8000
```

### 姝ラ 2锛氳闂?API 鏂囨。

鎵撳紑娴忚鍣ㄨ闂細http://localhost:8000/docs

### 姝ラ 3锛氭祴璇曢娴嬫帴鍙?
浣跨敤 Swagger UI 娴嬭瘯 `/predict` 鎺ュ彛銆?
---

## 馃摑 甯歌闂 FAQ

### Q1: 鏇挎崲鍚庣▼搴忔姤閿欐€庝箞鍔烇紵

**A**: 
1. 鎭㈠澶囦唤锛歚cp data/models/model_artifacts_backup.pkl data/models/model_artifacts.pkl`
2. 妫€鏌ユ柊妯″瀷鏄惁鍏煎
3. 鏌ョ湅閿欒淇℃伅

### Q2: 濡備綍鐭ラ亾鏂版ā鍨嬫槸鍚︽瘮鏃фā鍨嬪ソ锛?
**A**: 杩愯瀹屾暣娴嬭瘯骞舵瘮杈冭瘎浼版姤鍛娿€?
### Q3: 鍙互淇濈暀涓や釜妯″瀷鍚屾椂浣跨敤鍚楋紵

**A**: 鍙互锛?
```bash
# 淇濈暀鏃фā鍨?cp data/models/model_artifacts.pkl data/models/model_artifacts_old.pkl

# 娣诲姞鏂版ā鍨?cp ddos_detect_model.pkl data/models/model_artifacts_new.pkl
```

---

**绁濅綘鏇挎崲鎴愬姛锛?* 馃帀

---

**鏈€鍚庢洿鏂?*: 2026-04-04

