#!/bin/bash

# =====================================
# Script: lambda_update.sh
# =====================================

set -euo pipefail  # Encerra se houver erro, variável indefinida ou pipe falhar

# ----------------------------
# Configurações
# ----------------------------
FUNCTION_NAME="mega-sena-update-HelloWorldFunction-2nqbdesPpWpW"
REGION="sa-east-1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_DIR="$SCRIPT_DIR/../hello_world"
PACKAGE_DIR="$SCRIPT_DIR/../package"
ZIP_FILE="$SCRIPT_DIR/../function.zip"

# ----------------------------
# Verificar AWS CLI
# ----------------------------
if ! command -v aws &> /dev/null; then
    echo "Erro: AWS CLI não encontrada. Instale e configure antes de rodar."
    exit 1
fi

# ----------------------------
# Limpar pacotes antigos
# ----------------------------
echo "Limpando pacotes antigos..."
rm -rf "$PACKAGE_DIR" "$ZIP_FILE"
mkdir -p "$PACKAGE_DIR"

# ----------------------------
# Instalar dependências
# ----------------------------
if [ -f "$CODE_DIR/requirements.txt" ]; then
    echo "Instalando dependências no package..."
    
    # Criar virtualenv temporário
    TEMP_ENV="$SCRIPT_DIR/temp_env"
    python3 -m venv "$TEMP_ENV"
    source "$TEMP_ENV/bin/activate"
    
    pip install --upgrade pip
    pip install --upgrade -r "$CODE_DIR/requirements.txt" -t "$PACKAGE_DIR"
    
    deactivate
    rm -rf "$TEMP_ENV"
else
    echo "Nenhum requirements.txt encontrado em $CODE_DIR. Pulando instalação de dependências."
fi

# ----------------------------
# Copiar código da função
# ----------------------------
echo "Copiando código da função..."
cp -r "$CODE_DIR/"* "$PACKAGE_DIR/"

# ----------------------------
# Criar ZIP
# ----------------------------
echo "Criando arquivo ZIP..."
cd "$PACKAGE_DIR"
zip -r "$ZIP_FILE" . -x "*.pyc" "__pycache__/*"
cd "$SCRIPT_DIR"

# ----------------------------
# Verificar se o ZIP foi criado
# ----------------------------
if [ ! -f "$ZIP_FILE" ]; then
    echo "Erro: arquivo $ZIP_FILE não foi criado!"
    exit 1
fi
echo "ZIP criado com sucesso: $ZIP_FILE"

# ----------------------------
# Atualizar função Lambda
# ----------------------------
echo "Atualizando função Lambda..."

set +e  # para capturar erros sem interromper o script imediatamente
UPDATE_OUTPUT=$(aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$ZIP_FILE" \
    --region "$REGION" 2>&1)
STATUS=$?
set -e

if [ $STATUS -ne 0 ]; then
    echo "Erro ao atualizar Lambda:"
    echo "$UPDATE_OUTPUT"
    exit 1
fi

echo "Função Lambda atualizada com sucesso!"
