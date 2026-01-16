#!/bin/bash

# Configuration
IMAGE_NAME="informacast_dash"
CONTAINER_NAME="informacast_dash"
PORT="5082"

echo "--- Stopping existing container ---"
docker stop $CONTAINER_NAME 2>/dev/null
docker rm $CONTAINER_NAME 2>/dev/null

echo "--- Building Docker Image ---"
docker build -t $IMAGE_NAME .

echo "--- Starting Container on Port $PORT ---"
docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  -p $PORT:5082 \
  $IMAGE_NAME

echo "--- Network Validation (Internal) ---"
sleep 3
docker exec $CONTAINER_NAME nslookup api.icmobile.singlewire.com || echo "!!! DNS FAILED"
docker exec $CONTAINER_NAME curl -I https://api.icmobile.singlewire.com/api/v1/about || echo "!!! API UNREACHABLE"

echo "--- Done. Access via Reverse Proxy at https://galacticbacon.nic.edu/informacast/ ---"
docker logs --tail 10 $CONTAINER_NAME