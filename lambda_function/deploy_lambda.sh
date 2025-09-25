#!/bin/bash

FUNCTION_NAME="minha_lambda"
ZIP_FILE="lambda_package.zip"
HANDLER="lambda_function.lambda_handler"
ROLE="arn:aws:iam::000000000000:role/lambda-role"
S3_BUCKET="meu-bucket"
LOCALSTACK_URL="http://localhost:4566"

# 1. Criar o pacote da Lambda
echo "Empacotando função Lambda..."
rm -f $ZIP_FILE
rm -rf build
mkdir -p build
pip install --target ./build requests boto3 -q
cp lambda_function.py build/
cd build || exit
zip -r ../$ZIP_FILE . > /dev/null
cd ..

# 2. Criar ou atualizar a função Lambda com timeout maior
echo "Criando/atualizando função Lambda..."
aws --endpoint-url=$LOCALSTACK_URL lambda get-function --function-name $FUNCTION_NAME > /dev/null 2>&1
if [ $? -eq 0 ]; then
    aws --endpoint-url=$LOCALSTACK_URL lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://$ZIP_FILE
    aws --endpoint-url=$LOCALSTACK_URL lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --timeout 60
else
    aws --endpoint-url=$LOCALSTACK_URL lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime python3.11 \
        --role $ROLE \
        --handler $HANDLER \
        --zip-file fileb://$ZIP_FILE \
        --timeout 60
fi

# 3. Esperar função estar disponível
echo "Aguardando função estar disponível..."
while true; do
    aws --endpoint-url=$LOCALSTACK_URL lambda get-function --function-name $FUNCTION_NAME > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        break
    fi
    sleep 1
done

# 4. Invocar a função e exibir JSON
echo "Invocando função Lambda..."
aws --endpoint-url=$LOCALSTACK_URL lambda invoke \
    --function-name $FUNCTION_NAME \
    --payload '{}' response.json
cat response.json
rm -rf build
