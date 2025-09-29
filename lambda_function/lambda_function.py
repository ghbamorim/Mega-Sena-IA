import os
import json
import boto3
import logging
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET = os.getenv("S3_BUCKET", "meu-bucket")
DATASET_FILE = os.getenv("DATASET_FILE", "dataset.json")
REGION = os.getenv("REGION", "us-east-1")
LOCALSTACK_URL = os.getenv("LOCALSTACK_URL_CONTAINER", "http://localstack:4566")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")  # SQS queue URL

# API timeout
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))

s3 = boto3.client(
    "s3",
    endpoint_url=LOCALSTACK_URL,
    region_name=REGION
)

sqs = boto3.client(
    "sqs",
    endpoint_url=LOCALSTACK_URL,
    region_name=REGION
)

def lambda_handler(event, context):
    dataset = []
    try:
        logger.info(f"Reading {DATASET_FILE} from bucket {BUCKET}...")
        response = s3.get_object(Bucket=BUCKET, Key=DATASET_FILE)
        dataset = json.loads(response["Body"].read())
        logger.info(f"Dataset loaded. Total records: {len(dataset)}")
    except s3.exceptions.NoSuchKey:
        logger.warning(f"{DATASET_FILE} not found. Creating a new dataset...")
        dataset = []
    except Exception as e:
        logger.error(f"Error loading dataset: {e}")
        return {"dataset": dataset, "total_records": len(dataset)}

    last_number = dataset[0]["number"] if dataset else 0
    logger.info(f"Last contest in dataset: {last_number}")

    # Last contest from API
    try:
        r = requests.get(
            "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena",
            timeout=API_TIMEOUT
        )
        r.raise_for_status()
        last_concurso_api = int(r.json()["numero"])
        logger.info(f"Last contest from API: {last_concurso_api}")
    except Exception as e:
        logger.error(f"Error fetching last contest from API: {e}")
        last_concurso_api = last_number

    loop_count = 0
    max_iterations = 10
    for concurso_num in range(last_number + 1, last_concurso_api + 1):
        if loop_count >= max_iterations:
            break
        url = f"https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/{concurso_num}"
        try:
            r = requests.get(url, timeout=API_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if "listaDezenas" in data and data["listaDezenas"]:
                numbers = " ".join(data["listaDezenas"])
                dataset.insert(0, {
                    "number": int(data["numero"]),
                    "prompt": f"Digits: {data['dataApuracao']} -> Numbers:",
                    "completion": f" {numbers}"
                })
                logger.info(f"Contest {concurso_num} added to dataset.")
            else:
                logger.warning(f"No result for contest {concurso_num}")
        except Exception as e:
            logger.error(f"Error fetching contest {concurso_num}: {e}")
        loop_count += 1

    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=DATASET_FILE,
            Body=json.dumps(dataset, ensure_ascii=False).encode("utf-8")
        )
        logger.info(f"Dataset successfully updated. Total records: {len(dataset)}")
    except Exception as e:
        logger.error(f"Error saving dataset: {e}")

    if SQS_QUEUE_URL and loop_count > 0:
        try:
            sqs.send_message(
                QueueUrl=SQS_QUEUE_URL,
                MessageBody=json.dumps({"action": "train_model"})
            )
            logger.info("Message sent to SQS to trigger training.")
        except Exception as e:
            logger.error(f"Error sending SQS message: {e}. url: {SQS_QUEUE_URL}")

    return {"dataset": dataset[:5], "total_records": len(dataset)}
