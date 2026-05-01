import os
import time
import csv
import uuid
import socket
import numpy as np
from datetime import datetime
from collections import defaultdict
import dpkt

# ==============================================
# 📂 【你只需要改这两个路径 】
# ==============================================
# 自动监控的文件夹（成员1 放PCAP文件）
WATCH_FOLDER = r"C:\Users\susu\Desktop\auto_pcap"

# 输出CSV文件夹（成员2 来读取）
SHARE_FOLDER = r"C:\Users\susu\Desktop\share_csv"

# ==============================================
# CICFlowMeter 标准列名（格式100%符合要求）
# ==============================================
COLUMNS = [
    "Unnamed: 0", "Flow ID", "Source IP", "Source Port", "Destination IP", "Destination Port",
    "Protocol", "Timestamp", "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
    "Total Length of Fwd Packets", "Total Length of Bwd Packets", "Fwd Packet Length Max",
    "Fwd Packet Length Min", "Fwd Packet Length Mean", "Fwd Packet Length Std",
    "Bwd Packet Length Max", "Bwd Packet Length Min", "Bwd Packet Length Mean", "Bwd Packet Length Std",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std", "Flow IAT Max", "Flow IAT Min",
    "Fwd IAT Total", "Fwd IAT Mean", "Fwd IAT Std", "Fwd IAT Max", "Fwd IAT Min",
    "Bwd IAT Total", "Bwd IAT Mean", "Bwd IAT Std", "Bwd IAT Max", "Bwd IAT Min",
    "Fwd PSH Flags", "Bwd PSH Flags", "Fwd URG Flags", "Bwd URG Flags",
    "Fwd Header Length", "Bwd Header Length", "Fwd Packets/s", "Bwd Packets/s",
    "Min Packet Length", "Max Packet Length", "Packet Length Mean", "Packet Length Std", "Packet Length Variance",
    "FIN Flag Count", "SYN Flag Count", "RST Flag Count", "PSH Flag Count", "ACK Flag Count",
    "URG Flag Count", "CWE Flag Count", "ECE Flag Count", "Down/Up Ratio",
    "Average Packet Size", "Avg Fwd Segment Size", "Avg Bwd Segment Size",
    "Fwd Header Length.1", "Fwd Avg Bytes/Bulk", "Fwd Avg Packets/Bulk", "Fwd Avg Bulk Rate",
    "Bwd Avg Bytes/Bulk", "Bwd Avg Packets/Bulk", "Bwd Avg Bulk Rate",
    "Subflow Fwd Packets", "Subflow Fwd Bytes", "Subflow Bwd Packets", "Subflow Bwd Bytes",
    "Init_Win_bytes_forward", "Init_Win_bytes_backward", "act_data_pkt_fwd", "min_seg_size_forward",
    "Active Mean", "Active Std", "Active Max", "Active Min",
    "Idle Mean", "Idle Std", "Idle Max", "Idle Min",
    "SimillarHTTP", "Inbound", "Label"
]

# ==============================================
# 工具函数
# ==============================================
def inet_to_str(inet):
    try:
        return socket.inet_ntop(socket.AF_INET, inet)
    except:
        return socket.inet_ntop(socket.AF_INET6, inet)

def safe_div(a, b):
    return a / b if b != 0 else 0.0

def calc_stats(arr):
    if not arr:
        return 0, 0, 0, 0
    arr = np.array(arr, dtype=np.float64)
    return arr.max(), arr.min(), arr.mean(), arr.std()

# ==============================================
# 核心：PCAP → 标准CSV（文件名完全一样）
# ==============================================
def pcap_to_cic(pcap_path, csv_output_path):
    flows = defaultdict(lambda: {
        "src_ip": "", "src_port": 0, "dst_ip": "", "dst_port": 0, "proto": 0,
        "start_ts": None, "last_ts": None, "first_ts": None,
        "fwd_pkt_len": [], "fwd_iat": [], "fwd_header_len": [],
        "fwd_psh": 0, "fwd_urg": 0, "fwd_fin": 0, "fwd_syn": 0, "fwd_rst": 0, "fwd_ack": 0,
        "fwd_ece": 0, "fwd_cwr": 0, "fwd_init_win": -1, "fwd_act_data": 0, "fwd_min_seg": float('inf'),
        "bwd_pkt_len": [], "bwd_iat": [], "bwd_header_len": [],
        "bwd_psh": 0, "bwd_urg": 0, "bwd_fin": 0, "bwd_syn": 0, "bwd_rst": 0, "bwd_ack": 0,
        "bwd_ece": 0, "bwd_cwr": 0, "bwd_init_win": -1,
        "all_pkt_len": [], "flow_iat": []
    })

    with open(pcap_path, 'rb') as f:
        pcap = dpkt.pcap.Reader(f)
        prev_ts = None
        for ts, buf in pcap:
            try:
                eth = dpkt.ethernet.Ethernet(buf)
                if not isinstance(eth.data, (dpkt.ip.IP, dpkt.ip6.IP6)):
                    continue
                ip = eth.data
                src_ip = inet_to_str(ip.src)
                dst_ip = inet_to_str(ip.dst)
                proto = ip.p
                src_port = dst_port = 0
                tcp = udp = None

                if proto == 6:
                    tcp = ip.data
                    src_port = tcp.sport
                    dst_port = tcp.dport
                    pkt_len = len(ip.data)
                    header_len = tcp.off * 4
                elif proto == 17:
                    udp = ip.data
                    src_port = udp.sport
                    dst_port = udp.dport
                    pkt_len = len(ip.data)
                    header_len = 8
                else:
                    continue

                is_fwd = (src_ip, src_port) < (dst_ip, dst_port)
                flow_key = tuple(sorted([(src_ip, src_port), (dst_ip, dst_port)]) + [proto])
                flow = flows[flow_key]

                if flow["start_ts"] is None:
                    flow["src_ip"] = src_ip if is_fwd else dst_ip
                    flow["src_port"] = src_port if is_fwd else dst_port
                    flow["dst_ip"] = dst_ip if is_fwd else src_ip
                    flow["dst_port"] = dst_port if is_fwd else src_port
                    flow["proto"] = proto
                    flow["start_ts"] = ts
                    flow["first_ts"] = ts
                flow["last_ts"] = ts

                if prev_ts is not None:
                    iat = (ts - prev_ts) * 1e6
                    flow["flow_iat"].append(iat)
                prev_ts = ts

                if is_fwd:
                    flow["fwd_pkt_len"].append(pkt_len)
                    flow["fwd_header_len"].append(header_len)
                    if len(flow["fwd_iat"]) >= 1:
                        flow["fwd_iat"].append((ts - flow["last_ts"]) * 1e6)
                    else:
                        flow["fwd_iat"].append(0)
                    if tcp:
                        flow["fwd_psh"] += 1 if (tcp.flags & dpkt.tcp.TH_PUSH) else 0
                        flow["fwd_urg"] += 1 if (tcp.flags & dpkt.tcp.TH_URG) else 0
                        flow["fwd_fin"] += 1 if (tcp.flags & dpkt.tcp.TH_FIN) else 0
                        flow["fwd_syn"] += 1 if (tcp.flags & dpkt.tcp.TH_SYN) else 0
                        flow["fwd_rst"] += 1 if (tcp.flags & dpkt.tcp.TH_RST) else 0
                        flow["fwd_ack"] += 1 if (tcp.flags & dpkt.tcp.TH_ACK) else 0
                        flow["fwd_ece"] += 1 if (tcp.flags & 0x40) else 0
                        flow["fwd_cwr"] += 1 if (tcp.flags & 0x80) else 0
                        if flow["fwd_init_win"] == -1:
                            flow["fwd_init_win"] = tcp.win
                        if pkt_len > header_len:
                            flow["fwd_act_data"] += 1
                        flow["fwd_min_seg"] = min(flow["fwd_min_seg"], pkt_len - header_len)
                else:
                    flow["bwd_pkt_len"].append(pkt_len)
                    flow["bwd_header_len"].append(header_len)
                    if len(flow["bwd_iat"]) >= 1:
                        flow["bwd_iat"].append((ts - flow["last_ts"]) * 1e6)
                    else:
                        flow["bwd_iat"].append(0)
                    if tcp:
                        flow["bwd_psh"] += 1 if (tcp.flags & dpkt.tcp.TH_PUSH) else 0
                        flow["bwd_urg"] += 1 if (tcp.flags & dpkt.tcp.TH_URG) else 0
                        flow["bwd_fin"] += 1 if (tcp.flags & dpkt.tcp.TH_FIN) else 0
                        flow["bwd_syn"] += 1 if (tcp.flags & dpkt.tcp.TH_SYN) else 0
                        flow["bwd_rst"] += 1 if (tcp.flags & dpkt.tcp.TH_RST) else 0
                        flow["bwd_ack"] += 1 if (tcp.flags & dpkt.tcp.TH_ACK) else 0
                        if flow["bwd_init_win"] == -1:
                            flow["bwd_init_win"] = tcp.win

                flow["all_pkt_len"].append(pkt_len)
            except Exception:
                continue

    with open(csv_output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        idx = 0
        for key, flow in flows.items():
            row = {c: 0 for c in COLUMNS}
            row["Unnamed: 0"] = idx
            row["Flow ID"] = f"{flow['src_ip']}:{flow['src_port']}-{flow['dst_ip']}:{flow['dst_port']}"
            row["Source IP"] = flow["src_ip"]
            row["Source Port"] = flow["src_port"]
            row["Destination IP"] = flow["dst_ip"]
            row["Destination Port"] = flow["dst_port"]
            row["Protocol"] = flow["proto"]
            row["Timestamp"] = datetime.fromtimestamp(flow["first_ts"]).strftime("%Y-%m-%d %H:%M:%S")
            row["Flow Duration"] = int((flow["last_ts"] - flow["start_ts"]) * 1e6)
            row["Label"] = "BENIGN"
            row["Inbound"] = 1 if flow["dst_ip"].startswith(("192.168.", "172.16.", "10.")) else 0

            fwd_pkts = len(flow["fwd_pkt_len"])
            bwd_pkts = len(flow["bwd_pkt_len"])
            total_fwd_bytes = sum(flow["fwd_pkt_len"])
            total_bwd_bytes = sum(flow["bwd_pkt_len"])
            total_pkts = fwd_pkts + bwd_pkts
            total_bytes = total_fwd_bytes + total_bwd_bytes
            duration_sec = safe_div(row["Flow Duration"], 1e6)

            row["Total Fwd Packets"] = fwd_pkts
            row["Total Backward Packets"] = bwd_pkts
            row["Total Length of Fwd Packets"] = total_fwd_bytes
            row["Total Length of Bwd Packets"] = total_bwd_bytes

            fmax, fmin, favg, fstd = calc_stats(flow["fwd_pkt_len"])
            bmax, bmin, bavg, bstd = calc_stats(flow["bwd_pkt_len"])
            row["Fwd Packet Length Max"] = fmax
            row["Fwd Packet Length Min"] = fmin
            row["Fwd Packet Length Mean"] = favg
            row["Fwd Packet Length Std"] = fstd
            row["Bwd Packet Length Max"] = bmax
            row["Bwd Packet Length Min"] = bmin
            row["Bwd Packet Length Mean"] = bavg
            row["Bwd Packet Length Std"] = bstd

            row["Flow Bytes/s"] = safe_div(total_bytes, duration_sec)
            row["Flow Packets/s"] = safe_div(total_pkts, duration_sec)
            row["Fwd Packets/s"] = safe_div(fwd_pkts, duration_sec)
            row["Bwd Packets/s"] = safe_div(bwd_pkts, duration_sec)

            aimax, aimin, aavg, astd = calc_stats(flow["flow_iat"])
            row["Flow IAT Max"] = aimax
            row["Flow IAT Min"] = aimin
            row["Flow IAT Mean"] = aavg
            row["Flow IAT Std"] = astd

            fimax, fimin, fiavg, fistd = calc_stats(flow["fwd_iat"])
            bimax, bimin, biavg, bistd = calc_stats(flow["bwd_iat"])
            row["Fwd IAT Max"] = fimax
            row["Fwd IAT Min"] = fimin
            row["Fwd IAT Mean"] = fiavg
            row["Fwd IAT Std"] = fistd
            row["Fwd IAT Total"] = sum(flow["fwd_iat"])
            row["Bwd IAT Max"] = bimax
            row["Bwd IAT Min"] = bimin
            row["Bwd IAT Mean"] = biavg
            row["Bwd IAT Std"] = bistd
            row["Bwd IAT Total"] = sum(flow["bwd_iat"])

            row["Fwd PSH Flags"] = flow["fwd_psh"]
            row["Bwd PSH Flags"] = flow["bwd_psh"]
            row["Fwd URG Flags"] = flow["fwd_urg"]
            row["Bwd URG Flags"] = flow["bwd_urg"]
            row["FIN Flag Count"] = flow["fwd_fin"] + flow["bwd_fin"]
            row["SYN Flag Count"] = flow["fwd_syn"] + flow["bwd_syn"]
            row["RST Flag Count"] = flow["fwd_rst"] + flow["bwd_rst"]
            row["PSH Flag Count"] = flow["fwd_psh"] + flow["bwd_psh"]
            row["ACK Flag Count"] = flow["fwd_ack"] + flow["bwd_ack"]
            row["URG Flag Count"] = flow["fwd_urg"] + flow["bwd_urg"]
            row["CWE Flag Count"] = flow["fwd_cwr"] + flow["bwd_cwr"]
            row["ECE Flag Count"] = flow["fwd_ece"] + flow["bwd_ece"]

            row["Fwd Header Length"] = sum(flow["fwd_header_len"])
            row["Bwd Header Length"] = sum(flow["bwd_header_len"])
            row["Fwd Header Length.1"] = sum(flow["fwd_header_len"])

            amax, amin, aavg, astd = calc_stats(flow["all_pkt_len"])
            row["Max Packet Length"] = amax
            row["Min Packet Length"] = amin
            row["Packet Length Mean"] = aavg
            row["Packet Length Std"] = astd
            row["Packet Length Variance"] = astd ** 2

            row["Down/Up Ratio"] = safe_div(bwd_pkts, fwd_pkts)
            row["Average Packet Size"] = safe_div(total_bytes, total_pkts)
            row["Avg Fwd Segment Size"] = safe_div(total_fwd_bytes, fwd_pkts)
            row["Avg Bwd Segment Size"] = safe_div(total_bwd_bytes, bwd_pkts)

            row["Subflow Fwd Packets"] = fwd_pkts
            row["Subflow Fwd Bytes"] = total_fwd_bytes
            row["Subflow Bwd Packets"] = bwd_pkts
            row["Subflow Bwd Bytes"] = total_bwd_bytes

            row["Init_Win_bytes_forward"] = flow["fwd_init_win"] if flow["fwd_init_win"] != -1 else 0
            row["Init_Win_bytes_backward"] = flow["bwd_init_win"] if flow["bwd_init_win"] != -1 else 0
            row["act_data_pkt_fwd"] = flow["fwd_act_data"]
            row["min_seg_size_forward"] = flow["fwd_min_seg"] if flow["fwd_min_seg"] != float('inf') else 0

            row["Active Mean"] = row["Flow Duration"]
            row["Active Std"] = 0
            row["Active Max"] = row["Flow Duration"]
            row["Active Min"] = row["Flow Duration"]
            row["Idle Mean"] = 0
            row["Idle Std"] = 0
            row["Idle Max"] = 0
            row["Idle Min"] = 0

            writer.writerow(row)
            idx += 1

# ==============================================
# 自动监控文件夹（核心）
# ==============================================
def start_watcher():
    os.makedirs(WATCH_FOLDER, exist_ok=True)
    os.makedirs(SHARE_FOLDER, exist_ok=True)

    print("=" * 60)
    print("🚀 自动 PCAP → CSV 中转服务已启动")
    print(f"📥 监控：{WATCH_FOLDER}")
    print(f"📤 输出：{SHARE_FOLDER}")
    print("✅ 文件名 1:1 完全一致")
    print("=" * 60)

    processed = set()

    while True:
        for file in os.listdir(WATCH_FOLDER):
            if file.lower().endswith(".pcap") and file not in processed:
                processed.add(file)
                pcap_path = os.path.join(WATCH_FOLDER, file)
                
                # 👇 这里保证 CSV 名字和 PCAP 完全一样
                base_name = os.path.splitext(file)[0]
                csv_name = base_name + ".csv"
                csv_path = os.path.join(SHARE_FOLDER, csv_name)

                print(f"\n🔍 处理：{file}")
                pcap_to_cic(pcap_path, csv_path)
                print(f"✅ 完成：{csv_name}（文件名完全一致）")

        time.sleep(1)

# ==============================================
# 启动
# ==============================================
if __name__ == "__main__":
    start_watcher()