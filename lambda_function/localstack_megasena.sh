#!/bin/bash
set -e

# CONFIGURAÇÃO
FUNCTION_NAME="megasena-lambda"
HANDLER="megasena_update.lambda_handler"
ZIP_FILE="megasena_lambda.zip"
EVENT_FILE="event.json"
BUCKET_NAME="megasena-bucket"
REGION="us-east-1"
PROFILE="localstack"
LOCALSTACK_URL="http://localhost:4566"

# Função para mostrar logs da Lambda em caso de erro
show_lambda_logs() {
    echo "Recuperando logs da função..."
    LOG_GROUP="/aws/lambda/$FUNCTION_NAME"

    STREAM_NAME=$(aws --endpoint-url=$LOCALSTACK_URL --region $REGION --profile $PROFILE logs describe-log-streams \
        --log-group-name "$LOG_GROUP" \
        --query 'logStreams[0].logStreamName' --output text 2>/dev/null || echo "")

    if [ -z "$STREAM_NAME" ]; then
        echo "Nenhum log encontrado ainda."
    else
        aws --endpoint-url=$LOCALSTACK_URL --region $REGION --profile $PROFILE logs get-log-events \
            --log-group-name "$LOG_GROUP" \
            --log-stream-name "$STREAM_NAME" \
            --query 'events[*].message' \
            --output text
    fi
}

# Passo 0: Remove função antiga (evita conflitos)
echo "Removendo função Lambda antiga, se existir..."
aws --endpoint-url=$LOCALSTACK_URL --region $REGION --profile $PROFILE lambda delete-function --function-name $FUNCTION_NAME 2>/dev/null || true

# Passo 1: Cria bucket S3 (ignora se já existir)
echo "Criando bucket S3..."
aws --endpoint-url=$LOCALSTACK_URL --region $REGION --profile $PROFILE s3 mb s3://$BUCKET_NAME || true

# Passo 2: Empacota Lambda
echo "Empacotando Lambda..."
rm -rf package
rm -f $ZIP_FILE
mkdir package
pip install -r requirements.txt -t package/
cp megasena_update.py package/
cd package
zip -r9 ../$ZIP_FILE .
cd ..

# Passo 3: Cria arquivo de evento se não existir
if [ ! -f "$EVENT_FILE" ]; then
    echo "{}" > $EVENT_FILE
fi

# Passo 4: Cria Lambda
echo "Criando Lambda..."
aws --endpoint-url=$LOCALSTACK_URL --region $REGION --profile $PROFILE lambda create-function \
    --function-name $FUNCTION_NAME \
    --runtime python3.10 \
    --role arn:aws:iam::000000000000:role/dummy-role \
    --handler $HANDLER \
    --zip-file fileb://$ZIP_FILE \
    --timeout 15

# Passo 5: Invoca Lambda e captura logs se falhar
echo "Invocando Lambda..."
set +e
aws --endpoint-url=$LOCALSTACK_URL --region $REGION --profile $PROFILE lambda invoke \
    --function-name $FUNCTION_NAME \
    --payload file://$EVENT_FILE \
    output.json
STATUS=$?
set -e

if [ $STATUS -ne 0 ]; then
    echo "Erro ao invocar Lambda! Mostrando logs:"
    show_lambda_logs
    exit $STATUS
fi

echo "Resultado em output.json:"
cat output.json
