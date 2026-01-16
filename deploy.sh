#!/bin/bash

# Configuration
CONTAINER_NAME="informacast_dash"
IMAGE_NAME="informacast_dash"

echo "--- 🛠️  Starting Deployment ---"

# 1. GitHub Sync
echo "Step 1: Syncing with GitHub..."
git add .

echo "Enter your commit message:"
read commit_msg

if [ -z "$commit_msg" ]; then
    commit_msg="Update: $(date +'%Y-%m-%d %H:%M')"
fi

git commit -m "$commit_msg"
git push

# 2. Docker Rebuild
echo "Step 2: Rebuilding Docker Container..."
docker stop $CONTAINER_NAME 2>/dev/null
docker rm $CONTAINER_NAME 2>/dev/null

# Rebuild without cache to ensure all file changes are captured
docker build --no-cache -t $IMAGE_NAME .

echo "Step 3: Starting Container..."
docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  -p 5082:5082 \
  $IMAGE_NAME

# 3. Health Verification
echo "Step 4: Verifying Service..."
sleep 5
RUNNING=$(docker inspect -f '{{.State.Running}}' $CONTAINER_NAME 2>/dev/null)

if [ "$RUNNING" == "true" ]; then
    echo "--- ✅ Deployment Complete! ---"
    echo "Container is UP and running."
    echo "Streaming logs now (Ctrl+C to stop watching)..."
    echo "----------------------------------------------"
    docker logs -f $CONTAINER_NAME
else
    echo "--- ❌ Deployment FAILED ---"
    echo "Container failed to start. Recent logs:"
    docker logs $CONTAINER_NAME
fi