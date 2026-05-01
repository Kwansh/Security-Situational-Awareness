import pika
import os

# ===================== MQ 配置（和队友完全一样） =====================
MQ_HOST = "gerbil.rmq.cloudamqp.com"
MQ_PORT = 5672
MQ_VHOST = "xycvxmzl"
MQ_USER = "xycvxmzl"
MQ_PASS = "M0mLslia3T2P1Yy7xkT15fC001sz0Kmo"
MQ_QUEUE = "flow_csv_queue"

# ===================== 接收 CSV（已适配队友发送格式） =====================
def on_message_received(ch, method, properties, body):
    try:
        # 解码队友发来的消息
        msg = body.decode("utf-8").strip()
        
        # 按换行切分（队友就是这么发的）
        parts = msg.split("\n", 1)
        if len(parts) < 2:
            print("⚠️ 格式错误")
            return

        # 第一行：CSV_CONTENT:/output/xxx.csv
        # 第二行：真正的CSV内容
        header = parts[0].strip()
        csv_content = parts[1]

        # 校验格式
        if not header.startswith("CSV_CONTENT:"):
            print("⚠️ 不是CSV文件")
            return

        print("\n📥 收到队友发送的流量特征CSV")

        # 保存目录（自动创建）
        save_dir = "data/ingest"
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, "analysis_ready.csv")

        # 写入文件
        with open(save_path, "w", encoding="utf-8", newline="") as f:
            f.write(csv_content)

        print(f"✅ 保存成功：{save_path}")
        print("🚀 可以直接开始攻击检测！")
        print("=" * 60)

    except Exception as e:
        print(f"❌ 解析失败：{e}")

# ===================== 启动监听 =====================
def start_consumer():
    credentials = pika.PlainCredentials(MQ_USER, MQ_PASS)
    parameters = pika.ConnectionParameters(
        host=MQ_HOST,
        port=MQ_PORT,
        virtual_host=MQ_VHOST,
        credentials=credentials,
        heartbeat=600
    )

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue=MQ_QUEUE, durable=True)

    channel.basic_consume(
        queue=MQ_QUEUE,
        on_message_callback=on_message_received,
        auto_ack=True
    )

    print("🚀 攻击检测端已启动，等待队友发送CSV...")
    print("=" * 60)
    channel.start_consuming()

if __name__ == "__main__":
    start_consumer()
