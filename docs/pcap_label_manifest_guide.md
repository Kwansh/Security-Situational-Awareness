# PCAP 标签清单说明

这份文档只说明一件事：当我们使用 `PCAP` 直接训练模型时，标签清单 `label_manifest` 应该怎么写。

## 1. 什么时候需要这份文件

如果训练数据是原始 `PCAP`，那么 `PCAP` 本身通常不带标签。
这时就需要一份标签清单，把“文件名”和“对应标签”对应起来。

如果训练数据已经是带 `Label` 列的 `CSV`，那就不需要这份清单。

## 2. 推荐使用 JSON

推荐格式是一个 JSON 对象，例如：

```json
{
  "capture_001.pcap": "BENIGN",
  "capture_002.pcap": "SYN_FLOOD",
  "capture_003.pcap": "UDP_FLOOD"
}
```

### 2.1 Key 怎么写

代码会按下面几种方式匹配：

1. 文件名本体
- 例如：`capture_001.pcap`

2. 不带后缀的文件名
- 例如：`capture_001`

3. 完整路径
- 例如：`F:/data/raw/pcap/capture_001.pcap`

### 2.2 Value 怎么写

`value` 就是标签名称，建议统一大写。

常见标签示例：
- `BENIGN`
- `SYN_FLOOD`
- `UDP_FLOOD`
- `DNS_FLOOD`
- `NTP_FLOOD`
- `PORT_SCAN`

标签名称没有硬性限制，但组内最好先统一命名规则。

## 3. 也可以使用 CSV

如果不想用 JSON，也可以用 CSV。

支持的列名：
- `file,label`
- `pcap,label`
- `name,label`

例如：

```csv
file,label
capture_001.pcap,BENIGN
capture_002.pcap,SYN_FLOOD
capture_003.pcap,UDP_FLOOD
```

## 4. 必须遵守的规则

1. 一个 `PCAP` 文件只对应一个标签
- 当前训练脚本是“文件级标签”
- 不会自动把一个文件拆成多个攻击类型

2. 标签清单要和 `PCAP` 文件对应
- 文件名写错会被当成缺失标签

3. 如果清单里没有某个文件
- 训练脚本会使用 `default_label`
- 默认值是 `BENIGN`

4. 如果整个目录都没有有效标签
- 训练会失败
- 因为模型不能只学到一个类别

## 5. 推荐目录结构

建议这样放：

```text
data/
  raw/
    pcap/
      capture_001.pcap
      capture_002.pcap
    label_manifest.json
```

或者：

```text
data/
  raw/
    pcap/
      capture_001.pcap
      capture_002.pcap
    label_manifest.csv
```

## 6. 可以直接发给同学的话

```text
我们现在是 PCAP 直接训练，不再转 CSV。
请你给我两样东西：
1. PCAP 文件
2. label_manifest.json 或 label_manifest.csv

JSON 格式示例：
{
  "capture_001.pcap": "BENIGN",
  "capture_002.pcap": "SYN_FLOOD"
}

或者 CSV：
file,label
capture_001.pcap,BENIGN
capture_002.pcap,SYN_FLOOD

注意：
- 一个 PCAP 只对应一个标签
- 标签建议统一大写
- 如果没有标注，训练会默认按 BENIGN 处理
```

## 7. 和当前代码的对应关系

- 读取逻辑：`src/data/pcap_dataset.py`
- 训练入口：`scripts/train.py`
- 标签清单参数：`--label_manifest`
- 默认标签：`--default_label BENIGN`
