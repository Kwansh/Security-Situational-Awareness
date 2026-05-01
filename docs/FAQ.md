# 甯歌闂瑙ｇ瓟 (FAQ)

## 瀹夎涓庨厤缃?
### Q1: 瀹夎渚濊禆鏃跺け璐ユ€庝箞鍔烇紵

**A**: 灏濊瘯浠ヤ笅瑙ｅ喅鏂规锛?
```bash
# 1. 鍗囩骇 pip
python -m pip install --upgrade pip

# 2. 浣跨敤鍥藉唴闀滃儚
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 閫愪釜瀹夎
pip install pandas numpy scikit-learn
pip install xgboost lightgbm
pip install fastapi uvicorn
```

### Q2: XGBoost 瀹夎澶辫触锛?
**A**: XGBoost 闇€瑕佺紪璇戠幆澧冿細

**Windows**:
```bash
pip install xgboost
```

**Linux**:
```bash
# 瀹夎缂栬瘧宸ュ叿
sudo apt-get install build-essential
pip install xgboost
```

**Mac**:
```bash
xcode-select --install
pip install xgboost
```

### Q3: 铏氭嫙鐜濡備綍鍒涘缓锛?
**A**: 

```bash
# 鍒涘缓铏氭嫙鐜
python -m venv .venv

# 婵€娲伙紙Windows锛?.venv\Scripts\activate

# 婵€娲伙紙Linux/Mac锛?source .venv/bin/activate
```

---

## 璁粌涓庨娴?
### Q4: 璁粌鏃跺唴瀛樹笉瓒筹紵

**A**: 闄愬埗璇诲彇鐨勬暟鎹噺锛?
```bash
python scripts/train.py --data_dir data/raw --test_size 0.2 --max-rows-per-file 50000
```

### Q5: 鐗瑰緛缁村害涓嶅尮閰嶏紵

**A**: 纭繚杈撳叆鐗瑰緛涓庤缁冩椂涓€鑷达細

```python
# 鏌ョ湅妯″瀷鏈熸湜鐨勭壒寰佹暟
import joblib
model_data = joblib.load('data/models/model_artifacts.pkl')
print(f"鐗瑰緛鏁伴噺锛歿len(model_data['feature_columns'])}")
```

### Q6: 棰勬祴缁撴灉涓虹┖锛?
**A**: 妫€鏌?CSV 鏂囦欢鏍煎紡锛?
- 纭繚鍖呭惈蹇呰鐨勫垪
- 纭繚娌℃湁绌哄€?- 纭繚鏁版嵁绫诲瀷姝ｇ‘

---

## API 鏈嶅姟

### Q7: API 鍚姩澶辫触锛?
**A**: 妫€鏌ョ鍙ｆ槸鍚﹁鍗犵敤锛?
```bash
# Windows
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :8000
```

鏇存崲绔彛锛?```bash
python run_api.py --port 8001
```

### Q8: WebSocket 杩炴帴鏂紑锛?
**A**: 妫€鏌ラ槻鐏璁剧疆鍜岀綉缁滆繛鎺ャ€?
### Q9: 鎵归噺棰勬祴涓婁紶澶辫触锛?
**A**: 妫€鏌ユ枃浠跺ぇ灏忛檺鍒讹細

```python
# FastAPI 榛樿闄愬埗 1MB锛屽彲淇敼
app = FastAPI()
app.config.max_upload_size = 10 * 1024 * 1024  # 10MB
```

---

## 妯″瀷鐩稿叧

### Q10: 濡備綍鏇挎崲妯″瀷锛?
**A**: 浣跨敤妯″瀷鏇挎崲鑴氭湰锛?
```bash
python scripts/swap_model.py --new-model new_model.pkl
```

### Q11: 妯″瀷绮惧害涓嬮檷锛?
**A**: 

1. 妫€鏌ユ暟鎹垎甯冩槸鍚﹀彉鍖?2. 閲嶆柊璁粌妯″瀷
3. 璋冩暣妯″瀷鍙傛暟

### Q12: 濡備綍淇濆瓨璁粌鏃ュ織锛?
**A**: 淇敼璁粌鑴氭湰娣诲姞鏃ュ織锛?
```python
import logging
logging.basicConfig(filename='train.log', level=logging.INFO)
```

---

## 閮ㄧ讲鐩稿叧

### Q13: Docker 閮ㄧ讲澶辫触锛?
**A**: 

```bash
# 1. 妫€鏌?Docker 鐗堟湰
docker --version

# 2. 閲嶆柊鏋勫缓
docker-compose build --no-cache

# 3. 鏌ョ湅鏃ュ織
docker-compose logs api
```

### Q14: 濡備綍閰嶇疆 HTTPS锛?
**A**: 浣跨敤 Nginx 鍙嶅悜浠ｇ悊锛?
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
    }
}
```

### Q15: 濡備綍璐熻浇鍧囪　锛?
**A**: 浣跨敤 Docker Compose 澶氬疄渚嬶細

```yaml
services:
  api:
    build: .
    deploy:
      replicas: 3
```

---

## 鎬ц兘浼樺寲

### Q16: 棰勬祴閫熷害鎱紵

**A**: 

1. 浣跨敤鏇磋交閲忕骇鐨勬ā鍨?2. 鍚敤妯″瀷閲忓寲
3. 浣跨敤 GPU 鍔犻€?
### Q17: 濡備綍浼樺寲鍐呭瓨浣跨敤锛?
**A**: 

```python
# 浣跨敤 float32 浠ｆ浛 float64
df = df.astype('float32')

# 鍒嗗潡澶勭悊澶ф暟鎹?for chunk in pd.read_csv('large.csv', chunksize=10000):
    process(chunk)
```

### Q18: 濡備綍鎻愰珮鍚炲悙閲忥紵

**A**: 

1. 浣跨敤寮傛澶勭悊
2. 鍚敤鎵归噺棰勬祴
3. 浣跨敤娑堟伅闃熷垪

---

## 鏁呴殰鎺掓煡

### Q19: 绋嬪簭宕╂簝鏃犻敊璇俊鎭紵

**A**: 鍚敤璇︾粏鏃ュ織锛?
```bash
python -u scripts/train.py 2>&1 | tee train.log
```

### Q20: 濡備綍鑾峰彇璋冭瘯淇℃伅锛?
**A**: 

```python
import sys
import traceback

try:
    # 浣犵殑浠ｇ爜
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
```

---

## 鍏朵粬闂

### Q21: 鏀寔鍝簺鏀诲嚮绫诲瀷锛?
**A**: 

- SYN Flood
- UDP Flood
- DNS Flood
- NTP Flood
- SQL Injection
- DDoS

### Q22: 濡備綍娣诲姞鏂扮殑鏀诲嚮绫诲瀷锛?
**A**: 

1. 鍦?`config.yaml` 涓坊鍔犳柊绫诲瀷
2. 鏇存柊 `LABEL_MAPPING`
3. 閲嶆柊璁粌妯″瀷

### Q23: 鏁版嵁鏍煎紡瑕佹眰锛?
**A**: 

鍙傝€?CICFlowMeter 杈撳嚭鏍煎紡锛屽繀椤诲寘鍚細
- Timestamp
- Destination Port
- Source Port
- Protocol
- SYN Flag Count
- Packet Length Mean
- Label

---

**闇€瑕佹洿澶氬府鍔╋紵**  
璇锋彁浜?Issue 鎴栬仈绯诲紑鍙戝洟闃熴€?
**鏈€鍚庢洿鏂?*: 2026-04-04


