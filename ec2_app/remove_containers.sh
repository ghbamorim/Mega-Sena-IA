echo "🔄 Removendo container $CONTAINER_NAME se existir..."
docker rm -f $CONTAINER_NAME 2>/dev/null || true

echo "🔄 Removendo e recriando stack..."
docker compose down || true
#docker compose up -d
