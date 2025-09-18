#!/bin/bash
# =====================================
# Script: lambda_execute.sh
# =====================================

set -e

# Configurações
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FUNCTION_NAME="mega-sena-update-HelloWorldFunction-2nqbdesPpWpW"
REGION="sa-east-1"
EVENT_FILE="$SCRIPT_DIR/../event.json"
RESPONSE_FILE="$SCRIPT_DIR/../response.json"

# Criar event.json se não existir
if [ ! -f "$EVENT_FILE" ]; then
    echo '{}' > "$EVENT_FILE"
fi

# Invocar função Lambda
aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --payload "file://$EVENT_FILE" \
    --cli-binary-format raw-in-base64-out \
    "$RESPONSE_FILE" \
    --region "$REGION"

# Mostrar resultado
cat "$RESPONSE_FILE"

# Exibir logs do CloudWatch
aws logs tail "/aws/lambda/$FUNCTION_NAME" --follow --region "$REGION"
