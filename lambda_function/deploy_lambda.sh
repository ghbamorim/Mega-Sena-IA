#!/bin/bash

set -e
trap 'echo "Erro no script. Abortando."; exit 1' ERR

# -----------------------------
# Carregar variáveis do .env
# -----------------------------
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo ".env não encontrado!"
    exit 1
fi

# -----------------------------
# Resetar LocalStack
# -----------------------------
LOCALSTACK_SERVICE_NAME=localstack

# echo "Parando e removendo container do LocalStack..."
# docker-compose stop $LOCALSTACK_SERVICE_NAME
# docker-compose rm -f $LOCALSTACK_SERVICE_NAME

# echo "Removendo volumes do LocalStack (exceto volumes do Postgres)..."
# docker volume ls -q | grep -v postgres | xargs -r docker volume rm

echo "Iniciando LocalStack novamente..."
docker-compose up -d $LOCALSTACK_SERVICE_NAME

echo "LocalStack resetado com sucesso!"

# -----------------------------
# Ativar venv ou criar se necessário
# -----------------------------
if [ -f ./venv/bin/activate ]; then
    source ./venv/bin/activate
else
    python3 -m venv venv
    source ./venv/bin/activate
    pip install --upgrade pip
fi

pip install -q boto3 requests

# -----------------------------
# 1. Criar bucket S3 (host)
# -----------------------------
echo "Verificando bucket S3..."
if ! aws --endpoint-url=$LOCALSTACK_URL_HOST s3api head-bucket --bucket $S3_BUCKET --region $REGION > /dev/null 2>&1; then
    echo "Bucket $S3_BUCKET não existe. Criando..."
    aws --endpoint-url=$LOCALSTACK_URL_HOST s3api create-bucket --bucket $S3_BUCKET --region $REGION
fi

# -----------------------------
# 2. Enviar dataset.json via Python
# -----------------------------
python3 upload_dataset.py

# -----------------------------
# 3. Criar fila SQS
# -----------------------------
echo "Verificando fila SQS..."
QUEUE_URL=$(aws --endpoint-url=$LOCALSTACK_URL_HOST sqs get-queue-url --queue-name $SQS_QUEUE --query 'QueueUrl' --output text 2>/dev/null || \
    aws --endpoint-url=$LOCALSTACK_URL_HOST sqs create-queue --queue-name $SQS_QUEUE --query 'QueueUrl' --output text)

echo "Fila SQS pronta: $QUEUE_URL"

# Enviar mensagem inicial
aws --endpoint-url=$LOCALSTACK_URL_HOST sqs send-message --queue-url $QUEUE_URL --message-body '{"init": "true"}'

# -----------------------------
# 4. Empacotar Lambda
# -----------------------------
rm -rf build $ZIP_FILE
mkdir -p build
pip install --target ./build requests boto3 -q
cp lambda_function.py build/
cd build || exit
zip -r ../$ZIP_FILE . > /dev/null
cd ..

# -----------------------------
# 5. Criar JSON de environment variables válidas para Lambda
# -----------------------------
cat > env.json <<EOF
{
    "Variables": {
        "S3_BUCKET": "$S3_BUCKET",
        "DATASET_FILE": "$DATASET_FILE",
        "REGION": "$REGION",
        "LOCALSTACK_URL_CONTAINER": "$LOCALSTACK_URL_CONTAINER",
        "SQS_QUEUE_URL": "$QUEUE_URL"
    }
}
EOF

# -----------------------------
# 6. Criar ou atualizar Lambda
# -----------------------------
if aws --endpoint-url=$LOCALSTACK_URL_HOST lambda get-function --function-name $FUNCTION_NAME --region $REGION > /dev/null 2>&1; then
    echo "Atualizando Lambda existente..."
    aws --endpoint-url=$LOCALSTACK_URL_HOST lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://$ZIP_FILE \
        --region $REGION

    aws --endpoint-url=$LOCALSTACK_URL_HOST lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --environment file://env.json \
        --region $REGION
else
    echo "Criando Lambda..."
    aws --endpoint-url=$LOCALSTACK_URL_HOST lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime python3.10 \
        --role $ROLE \
        --handler $HANDLER \
        --zip-file fileb://$ZIP_FILE \
        --timeout 60 \
        --environment file://env.json \
        --region $REGION
fi

# -----------------------------
# 7. Invocar Lambda (opcional)
# -----------------------------
# aws --endpoint-url=$LOCALSTACK_URL_HOST lambda invoke --function-name $FUNCTION_NAME --payload '{}' response.json --region $REGION --cli-binary-format raw-in-base64-out
# cat response.json
