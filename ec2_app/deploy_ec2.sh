#!/bin/bash
set -e

CONTAINER_NAME="localstack"
CONTAINER_DIR="/home/ec2-user/EC2_APP"
MODEL_CACHE_DIR="$CONTAINER_DIR/models/EleutherAI/gpt-neo-125M"
TMP_MODEL_DIR="/tmp/EleutherAI_gpt-neo-125M"

echo "🔧 Atualizando pacotes e certificados no container..."
docker exec -it $CONTAINER_NAME bash -c "apt-get update && apt-get install -y ca-certificates && update-ca-certificates"

echo "📂 Enviando arquivos essenciais..."
docker exec -it $CONTAINER_NAME mkdir -p $CONTAINER_DIR
docker cp "./app" "$CONTAINER_NAME:$CONTAINER_DIR/"
docker cp "./requirements.txt" "$CONTAINER_NAME:$CONTAINER_DIR/"
docker cp "./fastapi-mega-sena.service" "$CONTAINER_NAME:$CONTAINER_DIR/"
docker cp ".env" "$CONTAINER_NAME:$CONTAINER_DIR/"
echo "✅ Arquivos enviados com sucesso!"

echo "📦 Instalando dependências no container..."
docker exec -it $CONTAINER_NAME bash -c "cd $CONTAINER_DIR && pip install -r requirements.txt"

echo "⬇️ Instalando transformers no host (para download do modelo)..."
python3 -m pip install --upgrade pip
python3 -m pip install transformers

echo "⬇️ Baixando modelo EleutherAI/gpt-neo-125M localmente no host..."
mkdir -p $TMP_MODEL_DIR
python3 - <<EOF
from transformers import AutoModelForCausalLM, AutoTokenizer
from download_model import LOCAL_MODEL_DIR

AutoModelForCausalLM.from_pretrained('EleutherAI/gpt-neo-125M', cache_dir=LOCAL_MODEL_DIR)
AutoTokenizer.from_pretrained('EleutherAI/gpt-neo-125M', cache_dir=LOCAL_MODEL_DIR)
print(f"✅ Modelo baixado localmente em {LOCAL_MODEL_DIR}")
EOF

echo "📤 Transferindo modelo para o container..."
docker exec -it $CONTAINER_NAME mkdir -p $MODEL_CACHE_DIR
docker cp "$TMP_MODEL_DIR/." "$CONTAINER_NAME:$MODEL_CACHE_DIR/"
echo "✅ Modelo transferido para $MODEL_CACHE_DIR dentro do container"

echo "🛑 Finalizando possíveis uvicorn antigos..."
docker exec $CONTAINER_NAME bash -c '
PIDS=$(ps aux | grep "[u]vicorn app.main:app" | awk "{print \$2}")
for pid in $PIDS; do
    echo "Matando PID: $pid"
    kill -9 $pid || true
done
'

echo "🚀 Iniciando FastAPI..."
docker exec -d $CONTAINER_NAME bash -c "cd $CONTAINER_DIR && source .env && uvicorn app.main:app --host 0.0.0.0 --port 8000 > fastapi.log 2>&1 &"

sleep 5

echo "🔍 Verificando se FastAPI está ativo..."
HTTP_STATUS=$(docker exec -i $CONTAINER_NAME curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
    echo "✅ FastAPI está rodando!"
    echo ""
    echo "📜 Para ver os logs em tempo real, execute:"
    echo "docker exec -it $CONTAINER_NAME bash -c \"tail -f $CONTAINER_DIR/fastapi.log\""
else
    echo "❌ FastAPI não respondeu! Status HTTP: $HTTP_STATUS"
    echo "Veja os logs em fastapi.log dentro do container:"
    docker exec -it $CONTAINER_NAME cat $CONTAINER_DIR/fastapi.log
fi
