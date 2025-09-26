import os
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET = os.getenv("S3_BUCKET", "meu-bucket")
DATASET_FILE = os.getenv("DATASET_FILE", "dataset.json")
REGION = os.getenv("REGION", "us-east-1")
LOCALSTACK_URL = os.getenv("LOCALSTACK_URL_CONTAINER", "http://localstack:4566")

s3 = boto3.client(
    "s3",
    endpoint_url=LOCALSTACK_URL,
    region_name=REGION
)

def lambda_handler(event, context):
    dataset = []
    try:
        logger.info(f"Lendo {DATASET_FILE} do bucket {BUCKET}...")
        response = s3.get_object(Bucket=BUCKET, Key=DATASET_FILE)
        dataset = json.loads(response["Body"].read())
        logger.info(f"Dataset carregado. Total de registros: {len(dataset)}")
        for i, registro in enumerate(dataset[:5]):
            logger.info(f"[{i+1}] {registro}")
    except Exception as e:
        logger.error(f"Erro ao carregar dataset: {e}")

    return {"dataset": dataset[:5], "total_registros": len(dataset)}
