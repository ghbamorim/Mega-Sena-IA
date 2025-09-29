#!/bin/bash
set -e

# -----------------------------
# Load environment variables from .env
# -----------------------------
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo ".env not found!"
    exit 1
fi

# Use .env values with defaults if not set
CONTAINER_NAME="${CONTAINER_NAME:-localstack}"
CONTAINER_DIR="${CONTAINER_DIR:-/home/ec2-user/EC2_APP}"
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-$CONTAINER_DIR/models/EleutherAI/gpt-neo-125M}"
TMP_MODEL_DIR="${TMP_MODEL_DIR:-/tmp/EleutherAI_gpt-neo-125M}"
BASE_MODEL="${BASE_MODEL:-EleutherAI/gpt-neo-125M}"

# -----------------------------
# Update packages and certificates inside the container
# -----------------------------
echo "🔧 Updating packages and certificates in the container..."
docker exec -it $CONTAINER_NAME bash -c "apt-get update && apt-get install -y ca-certificates && update-ca-certificates"

# -----------------------------
# Upload essential files to the container
# -----------------------------
echo "📂 Uploading essential files..."
docker exec -it $CONTAINER_NAME mkdir -p $CONTAINER_DIR
docker cp "./app" "$CONTAINER_NAME:$CONTAINER_DIR/"
docker cp "./requirements.txt" "$CONTAINER_NAME:$CONTAINER_DIR/"
docker cp "./fastapi-mega-sena.service" "$CONTAINER_NAME:$CONTAINER_DIR/"
docker cp ".env" "$CONTAINER_NAME:$CONTAINER_DIR/"
echo "✅ Files uploaded successfully!"

# -----------------------------
# Install Python dependencies inside the container
# -----------------------------
echo "📦 Installing dependencies in the container..."
docker exec -it $CONTAINER_NAME bash -c "cd $CONTAINER_DIR && pip install -r requirements.txt"

# -----------------------------
# Install transformers library on host (for model download)
# -----------------------------
echo "⬇️ Installing transformers on the host (for model download)..."
python3 -m pip install --upgrade pip
python3 -m pip install transformers

# -----------------------------
# Download the model locally on the host
# -----------------------------
echo "⬇️ Downloading $BASE_MODEL model locally on the host..."
mkdir -p $TMP_MODEL_DIR
python3 - <<EOF
from transformers import AutoModelForCausalLM, AutoTokenizer
import os

# Define local cache directory
LOCAL_MODEL_DIR = "$TMP_MODEL_DIR"

# Download model and tokenizer
AutoModelForCausalLM.from_pretrained("$BASE_MODEL", cache_dir=LOCAL_MODEL_DIR)
AutoTokenizer.from_pretrained("$BASE_MODEL", cache_dir=LOCAL_MODEL_DIR)

print(f"✅ Model downloaded locally at {LOCAL_MODEL_DIR}")
EOF

# -----------------------------
# Transfer the model to the container
# -----------------------------
echo "📤 Transferring model to the container..."
docker exec -it $CONTAINER_NAME mkdir -p $MODEL_CACHE_DIR
docker cp "$TMP_MODEL_DIR/." "$CONTAINER_NAME:$MODEL_CACHE_DIR/"
echo "✅ Model transferred to $MODEL_CACHE_DIR inside the container"

# -----------------------------
# Terminate any old uvicorn processes inside the container
# -----------------------------
echo "🛑 Terminating any old uvicorn processes..."
docker exec $CONTAINER_NAME bash -c '
PIDS=$(ps aux | grep "[u]vicorn app.main:app" | awk "{print \$2}")
for pid in $PIDS; do
    echo "Killing PID: $pid"
    kill -9 $pid || true
done
'

# -----------------------------
# Start FastAPI inside the container
# -----------------------------
echo "🚀 Starting FastAPI..."
docker exec -d $CONTAINER_NAME bash -c "cd $CONTAINER_DIR && source .env && uvicorn app.main:app --host 0.0.0.0 --port 8000 > fastapi.log 2>&1 &"

sleep 5

# -----------------------------
# Check if FastAPI is running
# -----------------------------
echo "🔍 Checking if FastAPI is running..."
HTTP_STATUS=$(docker exec -i $CONTAINER_NAME curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
    echo "✅ FastAPI is running!"
    echo ""
    echo "📜 To view logs in real time, run:"
    echo "docker exec -it $CONTAINER_NAME bash -c \"tail -f $CONTAINER_DIR/fastapi.log\""
else
    echo "❌ FastAPI did not respond! HTTP status: $HTTP_STATUS"
    echo "Check the logs in fastapi.log inside the container:"
    docker exec -it $CONTAINER_NAME cat $CONTAINER_DIR/fastapi.log
fi
