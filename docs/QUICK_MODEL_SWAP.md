# 蹇€熸ā鍨嬫浛鎹㈡寚鍗?- 椤圭洰 2 鐨勭畝鍖栨枃妗?
## 鍓嶆彁鏉′欢

浣犳湁涓€涓柊鐨勬ā鍨嬫枃浠讹細**ddos_detect_model.pkl**

---

## 馃摛 绗竴姝ワ細涓婁紶鏂版ā鍨嬫枃浠?
### 鏂规硶 A锛氭嫋鎷戒笂浼狅紙鏈€绠€鍗曪級

1. **鎵撳紑 VSCode**锛岀‘淇濇墦寮€浜嗛」鐩?2. **鎵撳紑鏂囦欢璧勬簮绠＄悊鍣?*锛圵indows锛夋垨 **Finder**锛圡ac锛?3. **鎵惧埌浣犵殑鏂囦欢** `ddos_detect_model.pkl`
4. **鎷栨嫿鏂囦欢**鍒?VSCode 宸︿晶鐨勬枃浠舵爲涓紙鏀惧埌椤圭洰鏍圭洰褰曪級

### 鏂规硶 B锛氬鍒剁矘璐?
1. 鍦ㄦ枃浠惰祫婧愮鐞嗗櫒涓?**鍙抽敭澶嶅埗** `ddos_detect_model.pkl`
2. 鍦?VSCode 涓寜 `Ctrl+V` 绮樿创

---

## 馃攧 绗簩姝ワ細鏇挎崲鏃фā鍨?
### 閫夐」 1锛氱洿鎺ヨ鐩栵紙鎺ㄨ崘锛?
1. 鍦?VSCode 鏂囦欢鏍戜腑鎵惧埌 `data/models/model_artifacts.pkl`
2. **鍙抽敭** 鈫?**鍒犻櫎**
3. 鎵惧埌 `ddos_detect_model.pkl`
4. **鍙抽敭** 鈫?**閲嶅懡鍚?*
5. 鏀逛负 `model_artifacts.pkl`
6. 绉诲姩鍒?`data/models/` 鐩綍

### 閫夐」 2锛氫繚鐣欏浠斤紙瀹夊叏锛?
1. 鎵惧埌 `data/models/model_artifacts.pkl`
2. **鍙抽敭** 鈫?**閲嶅懡鍚?*
3. 鏀逛负 `model_artifacts_backup.pkl`
4. 鎵惧埌 `ddos_detect_model.pkl`
5. **鍙抽敭** 鈫?**閲嶅懡鍚?*
6. 鏀逛负 `model_artifacts.pkl`
7. 绉诲姩鍒?`data/models/` 鐩綍

---

## 鉁?绗笁姝ワ細楠岃瘉妯″瀷

### 鍦?VSCode 缁堢涓繍琛岋細

鎸?`` Ctrl + ` `` 鎵撳紑缁堢锛岀劧鍚庤緭鍏ワ細

```bash
python3 -c "import joblib; model = joblib.load('data/models/model_artifacts.pkl'); print('鉁?妯″瀷鍔犺浇鎴愬姛锛?)"
```

**濡傛灉鐪嬪埌** `鉁?妯″瀷鍔犺浇鎴愬姛锛乣 **璇存槑鏇挎崲鎴愬姛锛?*

---

## 馃И 绗洓姝ワ細娴嬭瘯瀹屾暣鍔熻兘

### 杩愯 API 鏈嶅姟锛?
```bash
python run_api.py --host 0.0.0.0 --port 8000
```

鐒跺悗璁块棶 http://localhost:8000/docs 娴嬭瘯 API銆?
---

## 鈿狅笍 甯歌闂

### 闂 1锛氭壘涓嶅埌 ddos_detect_model.pkl 鏂囦欢

**瑙ｅ喅**锛氱‘淇濇枃浠跺凡缁忎笂浼犲埌椤圭洰鏍圭洰褰曘€?
### 闂 2锛氭ā鍨嬪姞杞藉け璐?
**鍙兘鍘熷洜**锛?- 鏂囦欢鎹熷潖
- 妯″瀷鏍煎紡涓嶅吋瀹?
**瑙ｅ喅**锛?```bash
# 鎭㈠鏃фā鍨?cp data/models/model_artifacts_backup.pkl data/models/model_artifacts.pkl
```

---

## 馃摑 鏇挎崲瀹屾垚娓呭崟

- [ ] 鏂版ā鍨嬫枃浠跺凡涓婁紶
- [ ] 鏃фā鍨嬪凡澶囦唤锛堝彲閫夛級
- [ ] 鏂版ā鍨嬪凡閲嶅懡鍚嶅苟鏀惧叆 data/models/
- [ ] 杩愯楠岃瘉鍛戒护鎴愬姛
- [ ] 杩愯瀹屾暣绯荤粺娴嬭瘯鎴愬姛

**鍏ㄩ儴鎵撳嬀璇存槑鏇挎崲鎴愬姛锛?* 馃帀

---

**闇€瑕佸府鍔╋紵闅忔椂鎻愰棶锛?* 馃殌

