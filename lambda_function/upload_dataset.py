import os
import boto3

S3_BUCKET = os.getenv("S3_BUCKET", "meu-bucket")
DATASET_FILE = os.getenv("DATASET_FILE", "dataset.json")
LOCALSTACK_URL = os.getenv("LOCALSTACK_URL_HOST", "http://localhost:4566")
REGION = os.getenv("REGION", "us-east-1")

s3 = boto3.client(
    "s3",
    endpoint_url=LOCALSTACK_URL,
    region_name=REGION
)

# Sempre sobrescreve o dataset
with open(DATASET_FILE, "rb") as f:
    s3.put_object(Bucket=S3_BUCKET, Key=DATASET_FILE, Body=f)

print(f"{DATASET_FILE} enviado com sucesso para {S3_BUCKET}.")
