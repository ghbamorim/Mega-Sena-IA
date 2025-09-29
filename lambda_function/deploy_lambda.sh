#!/bin/bash
set -e
trap 'echo "Error in script. Aborting."; exit 1' ERR

# -----------------------------
# Load variables from .env
# -----------------------------
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo ".env not found!"
    exit 1
fi

# -----------------------------
# Reset LocalStack
# -----------------------------
LOCALSTACK_SERVICE_NAME=localstack
echo "🔄 Removing existing LocalStack container (if any)..."
docker rm -f $LOCALSTACK_SERVICE_NAME 2>/dev/null || true

echo "🚀 Starting LocalStack..."
docker compose up -d $LOCALSTACK_SERVICE_NAME

# Wait until LocalStack is fully ready
echo "⏳ Waiting for LocalStack to be ready..."
until curl -s $LOCALSTACK_URL_HOST/_localstack/health | grep '"services":.*"running"' >/dev/null; do
    sleep 3
done
echo "✅ LocalStack is ready!"

# -----------------------------
# Activate virtual environment
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
# 1. Create S3 bucket
# -----------------------------
echo "📦 Checking S3 bucket..."
if ! aws --endpoint-url=$LOCALSTACK_URL_HOST s3api head-bucket --bucket $S3_BUCKET --region $REGION > /dev/null 2>&1; then
    echo "📂 Bucket $S3_BUCKET does not exist. Creating..."
    aws --endpoint-url=$LOCALSTACK_URL_HOST s3api create-bucket --bucket $S3_BUCKET --region $REGION
fi

# -----------------------------
# 2. Upload dataset.json
# -----------------------------
echo "📤 Uploading dataset..."
python3 upload_dataset.py

# -----------------------------
# 3. Create SQS queue
# -----------------------------
echo "📨 Checking SQS queue..."
QUEUE_URL=$(aws --endpoint-url=$LOCALSTACK_URL_HOST sqs get-queue-url --queue-name $SQS_QUEUE --query 'QueueUrl' --output text 2>/dev/null || \
    aws --endpoint-url=$LOCALSTACK_URL_HOST sqs create-queue --queue-name $SQS_QUEUE --query 'QueueUrl' --output text)
echo "✅ SQS queue ready: $QUEUE_URL"

# Send initial message
aws --endpoint-url=$LOCALSTACK_URL_HOST sqs send-message --queue-url $QUEUE_URL --message-body '{"init": "true"}'

# -----------------------------
# 4. Package Lambda
# -----------------------------
echo "📦 Packaging Lambda..."
rm -rf build $ZIP_FILE
mkdir -p build
pip install --target ./build requests boto3 -q
cp lambda_function.py build/
cd build || exit
zip -r ../$ZIP_FILE . > /dev/null
cd ..

# -----------------------------
# 5. Create env.json for Lambda
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
# 6. Create or update Lambda
# -----------------------------
if aws --endpoint-url=$LOCALSTACK_URL_HOST lambda get-function --function-name $FUNCTION_NAME --region $REGION > /dev/null 2>&1; then
    echo "♻️ Updating existing Lambda..."
    aws --endpoint-url=$LOCALSTACK_URL_HOST lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://$ZIP_FILE \
        --region $REGION

    aws --endpoint-url=$LOCALSTACK_URL_HOST lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --environment file://env.json \
        --region $REGION
else
    echo "✨ Creating Lambda..."
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
# 7. Create EventBridge rule to trigger Lambda at midnight daily
# -----------------------------
echo "🕛 Scheduling Lambda via EventBridge..."
RULE_NAME="${FUNCTION_NAME}-daily-midnight"

# Only attempt if events service is enabled
if aws --endpoint-url=$LOCALSTACK_URL_HOST events list-rules --region $REGION > /dev/null 2>&1; then
    aws --endpoint-url=$LOCALSTACK_URL_HOST events put-rule \
        --name $RULE_NAME \
        --schedule-expression "cron(0 0 * * ? *)" \
        --state ENABLED \
        --region $REGION

    LAMBDA_ARN=$(aws --endpoint-url=$LOCALSTACK_URL_HOST lambda get-function \
        --function-name $FUNCTION_NAME --query 'Configuration.FunctionArn' --output text --region $REGION)

    aws --endpoint-url=$LOCALSTACK_URL_HOST events put-targets \
        --rule $RULE_NAME \
        --targets "Id"="1","Arn"="$LAMBDA_ARN" \
        --region $REGION

    # Grant permission for EventBridge to invoke Lambda
    RULE_ARN=$(aws --endpoint-url=$LOCALSTACK_URL_HOST events describe-rule \
        --name $RULE_NAME --query 'Arn' --output text --region $REGION)

    aws --endpoint-url=$LOCALSTACK_URL_HOST lambda add-permission \
        --function-name $FUNCTION_NAME \
        --statement-id "${RULE_NAME}-permission" \
        --action "lambda:InvokeFunction" \
        --principal events.amazonaws.com \
        --source-arn "$RULE_ARN" \
        --region $REGION

    echo "✅ Lambda scheduled to run daily at midnight."
else
    echo "⚠️ EventBridge service not enabled in LocalStack. Skipping Lambda scheduling."
fi
