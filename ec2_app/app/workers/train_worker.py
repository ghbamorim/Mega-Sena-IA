import os
import json
import time
import requests
import boto3
import logging
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger("sqs_worker")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
TRAIN_ENDPOINT = os.getenv("TRAIN_ENDPOINT", "http://localhost:8000/train")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
SQS_ENDPOINT = os.getenv("SQS_ENDPOINT", "http://localhost:4566")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

if not SQS_QUEUE_URL:
    raise ValueError("SQS_QUEUE_URL environment variable is required")

sqs = boto3.client(
    "sqs",
    endpoint_url=SQS_ENDPOINT,
    region_name=REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
)

class SQSWorker:
    def __init__(self, queue_url, train_endpoint, batch_size=10, wait_time=20, poll_interval=5):
        self.queue_url = queue_url
        self.train_endpoint = train_endpoint
        self.batch_size = batch_size
        self.wait_time = wait_time
        self.poll_interval = poll_interval

    def poll_messages(self):
        logger.info("SQS FIFO worker started...")
        while True:
            try:
                response = sqs.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=self.batch_size,
                    WaitTimeSeconds=self.wait_time,
                    MessageAttributeNames=['All'],
                    AttributeNames=['All']
                )
            except (BotoCoreError, ClientError) as e:
                logger.error(f"Error receiving messages from SQS: {e}")
                time.sleep(self.poll_interval)
                continue

            messages = response.get("Messages", [])
            if not messages:
                continue
            
            self.process_latest_message(messages)

            time.sleep(self.poll_interval)

    def process_latest_message(self, messages):
        train_messages = []
        other_messages = []
        
        for msg in messages:
            try:
                body = json.loads(msg.get("Body", "{}"))
                if body.get("action") == "train_model":
                    train_messages.append(msg)
                else:
                    other_messages.append(msg)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in message body: {msg.get('Body')}")
                continue

        if not train_messages:
            return
        
        train_messages.sort(key=lambda m: int(m['Attributes']['SentTimestamp']), reverse=True)

        latest_msg = train_messages[0]
        old_msgs = train_messages[1:]
        
        if self.trigger_training():
            self.delete_message(latest_msg["ReceiptHandle"])
            logger.info("Processed latest training message successfully.")          
            self.delete_batch_messages(old_msgs)
        else:
            logger.error("Failed to process latest training message; old messages remain in queue.")
        
        # for msg in other_messages:
        #     logger.info(f"Skipping unknown action message: {msg.get('Body')}")

    def trigger_training(self):
        """Call the training endpoint with retries"""
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                r = requests.post(self.train_endpoint, timeout=60)
                if r.status_code == 200:
                    logger.info("Training successfully triggered!")
                    return True
                else:
                    logger.error(f"Error triggering training (status {r.status_code}): {r.text}")
            except requests.RequestException as e:
                logger.error(f"Exception calling endpoint (attempt {attempt}): {e}")
            time.sleep(2 ** attempt)  # exponential backoff
        return False

    def delete_message(self, receipt_handle):
        """Delete a single SQS message"""
        try:
            sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)
            logger.info("Message deleted from SQS")
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Error deleting message from SQS: {e}")

    def delete_batch_messages(self, messages):
        """Delete multiple messages in batches (up to 10)"""
        for i in range(0, len(messages), 10):
            batch = messages[i:i + 10]
            entries = [{"Id": str(idx), "ReceiptHandle": m["ReceiptHandle"]} for idx, m in enumerate(batch)]
            try:
                sqs.delete_message_batch(QueueUrl=self.queue_url, Entries=entries)
                logger.info(f"Deleted {len(entries)} old training messages from SQS")
            except (BotoCoreError, ClientError) as e:
                logger.error(f"Error deleting batch messages from SQS: {e}")

def start_worker():
    worker = SQSWorker(queue_url=SQS_QUEUE_URL, train_endpoint=TRAIN_ENDPOINT)
    worker.poll_messages()


if __name__ == "__main__":
    start_worker()
