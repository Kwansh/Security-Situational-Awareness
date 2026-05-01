# API 鎺ュ彛鏂囨。

## 鍩虹淇℃伅

- **Base URL**: `http://localhost:8000`
- **API 鐗堟湰**: 4.1.0
- **璁よ瘉**: 鏆傛棤锛堢敓浜х幆澧冨缓璁坊鍔狅級

---

## 馃搵 鎺ュ彛鍒楄〃

### 1. 鍋ュ悍妫€鏌?
**GET** `/health`

妫€鏌?API 鏈嶅姟鍜屾ā鍨嬪姞杞界姸鎬併€?
#### 鍝嶅簲

```json
{
  "status": "ok",
  "model_loaded": true,
  "artifact_path": "data/models/model_artifacts.pkl",
  "feature_count": 36
}
```

#### 鐘舵€佺爜

| 鐘舵€佺爜 | 璇存槑 |
|--------|------|
| 200 | 鏈嶅姟姝ｅ父 |
| 503 | 妯″瀷鏈姞杞?|

---

### 2. 妯″瀷鍏冩暟鎹?
**GET** `/metadata`

鑾峰彇妯″瀷鍏冩暟鎹俊鎭€?
#### 鍝嶅簲

```json
{
  "feature_columns": ["pkt_rate", "syn_rate", ...],
  "label_mapping": {"BENIGN": 0, "Syn": 1},
  "metrics": {
    "accuracy": 0.9950,
    "precision": 0.9948,
    "recall": 0.9950,
    "f1_score": 0.9948
  }
}
```

#### 鐘舵€佺爜

| 鐘舵€佺爜 | 璇存槑 |
|--------|------|
| 200 | 鎴愬姛 |
| 503 | 妯″瀷鏈姞杞?|

---

### 3. 鍗曟潯棰勬祴

**POST** `/predict`

瀵瑰崟鏉℃牱鏈繘琛屾敾鍑绘娴嬨€?
#### 璇锋眰浣?
```json
{
  "features": {
    "pkt_rate": 1000.0,
    "syn_rate": 500.0,
    "udp_rate": 200.0,
    "dns_rate": 50.0,
    "ntp_rate": 10.0,
    "avg_pkt_size": 500.0
  },
  "source": "api"
}
```

鎴?
```json
{
  "record": {
    "Flow Duration": 2000,
    "Total Fwd Packets": 5,
    "Total Backward Packets": 1,
    "Flow Bytes/s": 3.0,
    "Label": "BENIGN"
  },
  "source": "api"
}
```

#### 鍝嶅簲

```json
{
  "prediction": 1,
  "prediction_label": "Syn",
  "confidence": 0.690071,
  "timestamp": "2026-04-04T11:45:00+00:00",
  "is_attack": true,
  "event": {
    "timestamp": "2026-04-04T11:45:00+00:00",
    "prediction": 1,
    "prediction_label": "Syn",
    "confidence": 0.690071,
    "is_attack": true,
    "severity": "medium",
    "source": "api",
    "input_kind": "features"
  }
}
```

#### 鐘舵€佺爜

| 鐘舵€佺爜 | 璇存槑 |
|--------|------|
| 200 | 鎴愬姛 |
| 422 | 鐗瑰緛缁村害涓嶅尮閰?|
| 503 | 妯″瀷鏈姞杞?|

---

### 4. 鎵归噺棰勬祴

**POST** `/predict/batch`

涓婁紶 CSV 鏂囦欢杩涜鎵归噺棰勬祴銆?
#### 璇锋眰鍙傛暟

| 鍙傛暟 | 绫诲瀷 | 蹇呭～ | 璇存槑 |
|------|------|------|------|
| file | File | 鏄?| CSV 鏂囦欢 |
| source | String | 鍚?| 鏁版嵁鏉ユ簮锛岄粯璁?`batch_upload` |

#### 鍝嶅簲

```json
{
  "total": 100,
  "predictions": [
    {
      "index": 0,
      "prediction": 1,
      "prediction_label": "Syn",
      "confidence": 0.690071,
      "timestamp": "2026-04-04T11:45:00+00:00",
      "is_attack": true,
      "event": {...}
    }
  ],
  "dashboard_summary": {
    "total_events": 100,
    "attack_events": 80,
    "benign_events": 20,
    "attack_ratio": 0.8
  }
}
```

#### 鐘舵€佺爜

| 鐘舵€佺爜 | 璇存槑 |
|--------|------|
| 200 | 鎴愬姛 |
| 422 | CSV 鏍煎紡閿欒 |
| 503 | 妯″瀷鏈姞杞?|

---

### 5. 浠〃鏉挎憳瑕?
**GET** `/dashboard/summary`

鑾峰彇妫€娴嬬粺璁℃憳瑕併€?
#### 鍝嶅簲

```json
{
  "total_events": 100,
  "attack_events": 80,
  "benign_events": 20,
  "attack_ratio": 0.8,
  "labels": {
    "Syn": 50,
    "UDP": 30
  },
  "sources": {
    "api": 80,
    "batch_upload": 20
  },
  "last_event": {...}
}
```

---

### 6. 鏈€杩戜簨浠?
**GET** `/dashboard/events`

鑾峰彇鏈€杩戠殑妫€娴嬩簨浠躲€?
#### 璇锋眰鍙傛暟

| 鍙傛暟 | 绫诲瀷 | 蹇呭～ | 璇存槑 |
|------|------|------|------|
| limit | Integer | 鍚?| 杩斿洖鏁伴噺锛岄粯璁?100锛屾渶澶?200 |

#### 鍝嶅簲

```json
{
  "events": [
    {
      "timestamp": "2026-04-04T11:45:00+00:00",
      "prediction": 1,
      "prediction_label": "Syn",
      "confidence": 0.690071,
      "is_attack": true,
      "severity": "medium",
      "source": "api",
      "input_kind": "features"
    }
  ],
  "count": 100
}
```

---

### 7. WebSocket 瀹炴椂妫€娴?
**WS** `/ws`

閫氳繃 WebSocket 杩涜瀹炴椂妫€娴嬨€?
#### 杩炴帴

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
```

#### 鍙戦€佹秷鎭?
```json
{
  "features": {
    "pkt_rate": 1000.0,
    "syn_rate": 500.0
  },
  "source": "websocket"
}
```

鎴?
```json
{
  "record": {
    "Flow Duration": 2000,
    "Total Fwd Packets": 5
  },
  "source": "websocket"
}
```

#### 鎺ユ敹娑堟伅

```json
{
  "prediction": 1,
  "prediction_label": "Syn",
  "confidence": 0.690071,
  "timestamp": "2026-04-04T11:45:00+00:00",
  "is_attack": true,
  "event": {...},
  "dashboard_summary": {...}
}
```

#### 閿欒娑堟伅

```json
{
  "error": "Missing 'record' or 'features'."
}
```

---

### 8. 模型热重载
**POST** `/admin/reload-model`

在不重启 API 的情况下重新加载 `model_artifacts.pkl`。

#### 响应

```json
{
  "reloaded": true,
  "model_loaded": true,
  "artifact_path": "data/models/model_artifacts.pkl",
  "artifact_mtime": 1712200000.0
}
```

---

## 馃敡 閿欒澶勭悊

### 甯歌閿欒

| 閿欒 | 鐘舵€佺爜 | 璇存槑 | 瑙ｅ喅鏂规 |
|------|--------|------|----------|
| `Model artifacts are not loaded` | 503 | 妯″瀷鏈姞杞?| 妫€鏌ユā鍨嬫枃浠惰矾寰?|
| `Expected X features, got Y` | 422 | 鐗瑰緛缁村害涓嶅尮閰?| 妫€鏌ヨ緭鍏ョ壒寰佹暟閲?|
| `Missing 'record' or 'features'` | 422 | 缂哄皯蹇呰鍙傛暟 | 鎻愪緵 features 鎴?record |

### 閿欒鍝嶅簲鏍煎紡

```json
{
  "detail": "閿欒鎻忚堪淇℃伅"
}
```

---

## 馃摑 浣跨敤绀轰緥

### Python 绀轰緥

```python
import requests

# 鍗曟潯棰勬祴
response = requests.post(
    'http://localhost:8000/predict',
    json={
        'features': {
            'pkt_rate': 1000.0,
            'syn_rate': 500.0,
            'udp_rate': 200.0,
            'dns_rate': 50.0,
            'ntp_rate': 10.0,
            'avg_pkt_size': 500.0
        }
    }
)
result = response.json()
print(f"鏀诲嚮绫诲瀷锛歿result['prediction_label']}")
print(f"缃俊搴︼細{result['confidence']:.2%}")
```

### cURL 绀轰緥

```bash
# 鍋ュ悍妫€鏌?curl http://localhost:8000/health

# 鍗曟潯棰勬祴
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features": {"pkt_rate": 1000.0, "syn_rate": 500.0}}'

# 鎵归噺棰勬祴
curl -X POST http://localhost:8000/predict/batch \
  -F "file=@test_data.csv"

# 模型热重载
curl -X POST http://localhost:8000/admin/reload-model
```

---

**API 鏂囨。鐗堟湰**: 4.1.0  
**鏈€鍚庢洿鏂?*: 2026-04-04

