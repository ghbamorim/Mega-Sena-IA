# Uso de S3

USE_S3=True
S3_BUCKET=meu-bucket
DATASET_PATH_S3=dataset.json

# Caminho local (caso USE_S3=False)

DATASET_PATH_LOCAL=./dataset.json

# Diretório de saída do modelo fine-tuned

OUTPUT_DIR=./finetuned_mega

# Modelo base

BASE_MODEL=EleutherAI/gpt-neo-125M

# Lambda

FUNCTION_NAME=minha_lambda
ZIP_FILE=lambda_package.zip
HANDLER=lambda_function.lambda_handler
ROLE=arn:aws:iam::000000000000:role/lambda-role
API_TIMEOUT=30

# S3

S3_BUCKET=meu-bucket
DATASET_FILE=dataset.json
REGION=us-east-1

# LocalStack endpoints

LOCALSTACK_URL_HOST=http://localhost:4566
LOCALSTACK_URL_CONTAINER=http://localstack:4566
SQS_QUEUE=minha-fila-teste
SQS_QUEUE_URL=http://sqs.us-east-2.localhost.localstack.cloud:4566/000000000000/minha-fila-teste
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1
