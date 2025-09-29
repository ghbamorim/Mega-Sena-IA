#!/bin/bash
set -e

# Load variables from .env
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo ".env not found!"
    exit 1
fi

# Invoke Lambda and capture logs and payload
echo "Invoking Lambda $FUNCTION_NAME..."
OUTPUT=$(aws --endpoint-url=$LOCALSTACK_URL_HOST lambda invoke \
    --function-name $FUNCTION_NAME \
    --payload '{}' response.json \
    --log-type Tail \
    --region $REGION \
    --cli-binary-format raw-in-base64-out \
    --query 'LogResult' \
    --output text)

# Decode base64 logs
echo "=== EXECUTION LOGS ==="
echo $OUTPUT | base64 --decode
echo "======================"

# Show payload
echo "=== LAMBDA RETURN ==="
cat response.json
echo "====================="
