#!/bin/bash

set -e

# Carregar variáveis do .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo ".env não encontrado!"
    exit 1
fi

# Invocar Lambda e capturar logs e payload
echo "Invocando Lambda $FUNCTION_NAME..."
OUTPUT=$(aws --endpoint-url=$LOCALSTACK_URL_HOST lambda invoke \
    --function-name $FUNCTION_NAME \
    --payload '{}' response.json \
    --log-type Tail \
    --region $REGION \
    --cli-binary-format raw-in-base64-out \
    --query 'LogResult' \
    --output text)

# Decodificar logs base64
echo "=== LOGS DA EXECUÇÃO ==="
echo $OUTPUT | base64 --decode
echo "========================"

# Exibir payload
echo "=== RETORNO DA LAMBDA ==="
cat response.json
echo "=========================="



