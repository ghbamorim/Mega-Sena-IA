import os
import json
import time
import requests
import boto3
import logging

logging.basicConfig(level=logging.INFO)

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
TRAIN_ENDPOINT = os.getenv("TRAIN_ENDPOINT", "http://localhost:8000/train")

sqs = boto3.client(
    "sqs",
    endpoint_url=os.getenv("SQS_ENDPOINT", "http://localhost:4566"),
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

def poll_sqs():
    logging.info("Worker SQS iniciado...")
    while True:
        try:
            messages = sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20
            )
        except Exception as e:
            logging.error(f"Erro ao receber mensagens do SQS (QueueUrl={SQS_QUEUE_URL}): {e}")
            time.sleep(5)
            continue

        if "Messages" in messages:
            for msg in messages["Messages"]:
                body = json.loads(msg["Body"])
                if body.get("action") == "train_model":
                    try:
                        r = requests.post(TRAIN_ENDPOINT, timeout=60)
                        if r.status_code == 200:
                            logging.info("Treinamento disparado com sucesso!")
                        else:
                            logging.error(f"Erro ao disparar treinamento: {r.text}")
                    except Exception as e:
                        logging.error(f"Exception ao chamar endpoint: {e}")

                try:
                    sqs.delete_message(
                        QueueUrl=SQS_QUEUE_URL,
                        ReceiptHandle=msg["ReceiptHandle"]
                    )
                except Exception as e:
                    logging.error(f"Erro ao deletar mensagem do SQS (QueueUrl={SQS_QUEUE_URL}): {e}")
        time.sleep(5)

def start_worker():
    poll_sqs()
