echo "🔄 Removing container $CONTAINER_NAME if it exists..."
docker rm -f $CONTAINER_NAME 2>/dev/null || true

echo "🔄 Removing and recreating stack..."
docker compose down || true
#docker compose up -d
