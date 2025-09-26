#!/bin/bash

set -e
trap 'echo "Erro no script. Abortando."' ERR

# Carregar variáveis do .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo ".env não encontrado!"
    exit 1
fi

# Ativar venv ou criar se necessário
if [ -f ./venv/bin/activate ]; then
    source ./venv/bin/activate
else
    python3 -m venv venv
    source ./venv/bin/activate
fi
pip install -q boto3 requests

# 1. Criar bucket S3 (host)
echo "Verificando bucket S3..."
if ! aws --endpoint-url=$LOCALSTACK_URL_HOST s3api head-bucket --bucket $S3_BUCKET --region $REGION > /dev/null 2>&1; then
    echo "Bucket $S3_BUCKET não existe. Criando..."
    aws --endpoint-url=$LOCALSTACK_URL_HOST s3api create-bucket --bucket $S3_BUCKET --region $REGION
fi

# 2. Enviar dataset.json via Python
python3 upload_dataset.py

# 3. Empacotar Lambda
rm -rf build $ZIP_FILE
mkdir -p build
pip install --target ./build requests boto3 -q
cp lambda_function.py build/
cd build || exit
zip -r ../$ZIP_FILE . > /dev/null
cd ..

# 4. Criar ou atualizar Lambda
if aws --endpoint-url=$LOCALSTACK_URL_HOST lambda get-function --function-name $FUNCTION_NAME --region $REGION > /dev/null 2>&1; then
    aws --endpoint-url=$LOCALSTACK_URL_HOST lambda update-function-code --function-name $FUNCTION_NAME --zip-file fileb://$ZIP_FILE --region $REGION
else
    aws --endpoint-url=$LOCALSTACK_URL_HOST lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime python3.10 \
        --role $ROLE \
        --handler $HANDLER \
        --zip-file fileb://$ZIP_FILE \
        --timeout 60 \
        --region $REGION
fi

# 5. Invocar Lambda
#aws --endpoint-url=$LOCALSTACK_URL_HOST lambda invoke --function-name $FUNCTION_NAME --payload '{}' response.json --region $REGION --cli-binary-format raw-in-base64-out
#cat response.json
