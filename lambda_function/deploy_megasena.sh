#!/bin/bash
set -e

# Carrega variáveis do arquivo .env
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo ".env não encontrado! Saindo..."
    exit 1
fi

# CONFIGURAÇÃO
FUNCTION_NAME="megasena-lambda"
RUNTIME="python3.10"
HANDLER="megasena_update.lambda_handler"
ZIP_FILE="megasena_lambda.zip"
EVENT_FILE="event.json"

# Limpa builds antigos
rm -rf package
rm -f $ZIP_FILE

# Cria diretório temporário para dependências
mkdir package

# Instala dependências no package
pip install -r requirements.txt -t package/

# Copia código para package
cp megasena_update.py package/

# Cria o zip
cd package
zip -r9 ../$ZIP_FILE .
cd ..

# Cria o arquivo de evento se não existir
if [ ! -f "$EVENT_FILE" ]; then
    echo "{}" > $EVENT_FILE
fi

# Tenta criar a função Lambda
echo "Tentando criar a função Lambda..."
if aws lambda create-function \
    --function-name $FUNCTION_NAME \
    --runtime $RUNTIME \
    --role $ROLE_ARN \
    --handler $HANDLER \
    --zip-file fileb://$ZIP_FILE \
    --timeout 15 2>/dev/null; then
    echo "Função criada com sucesso!"
else
    echo "Função já existe, atualizando código..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://$ZIP_FILE
fi

# Invoca a função Lambda para testar
echo "Testando função Lambda..."
aws lambda invoke \
    --function-name $FUNCTION_NAME \
    --payload file://$EVENT_FILE \
    output.json

echo "Resultado em output.json:"
cat output.json
