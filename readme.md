# -----------------------------

# Configurações S3

# -----------------------------

USE_S3=true
S3_BUCKET=meu-bucket
DATASET_FILE=dataset.json # nome consistente para o dataset
DATASET_PATH_LOCAL=./dataset.json
OUTPUT_DIR=./finetuned_mega
BASE_MODEL=EleutherAI/gpt-neo-125M

# -----------------------------

# Lambda

# -----------------------------

FUNCTION_NAME=minha_lambda
ZIP_FILE=lambda_package.zip
HANDLER=lambda_function.lambda_handler
ROLE=arn:aws:iam::000000000000:role/lambda-role
API_TIMEOUT=30

# -----------------------------

# AWS / LocalStack

# -----------------------------

REGION=us-east-1
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

LOCALSTACK_URL_HOST=http://localhost:4566 # para host
LOCALSTACK_URL_CONTAINER=http://localstack:4566 # para outros containers

# -----------------------------

# SQS

# -----------------------------

SQS_QUEUE=minha-fila-teste
SQS_QUEUE_URL=http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/minha-fila-teste
