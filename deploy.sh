#!/bin/bash

CONTAINER_NAME="informacast_dash"
IMAGE_NAME="informacast_dash"

echo "--- 🛠️  Starting Deployment ---"

# 1. GitHub Sync
echo "Step 1: Syncing with GitHub..."
git add .

echo "Enter your commit message:"
read commit_msg
if [ -z "$commit_msg" ]; then commit_msg="Update: $(date +'%Y-%m-%d %H:%M')"; fi

git commit -m "$commit_msg"
git push

# 2. Docker Rebuild
echo "Step 2: Rebuilding Docker Container..."
docker stop $CONTAINER_NAME 2>/dev/null
docker rm $CONTAINER_NAME 2>/dev/null
docker build --no-cache -t $IMAGE_NAME .

echo "Step 3: Starting Container (Single Worker Mode)..."
# We add --workers 1 and --timeout 120 here
docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  -p 5082:5082 \
  $IMAGE_NAME \
  gunicorn --bind 0.0.0.0:5082 --workers 1 --timeout 120 app:app

# 3. Health Verification
echo "Step 4: Verifying Service..."
sleep 5
RUNNING=$(docker inspect -f '{{.State.Running}}' $CONTAINER_NAME 2>/dev/null)

if [ "$RUNNING" == "true" ]; then
    echo "--- ✅ Deployment Complete! ---"
    echo "Streaming logs now..."
    docker logs -f $CONTAINER_NAME
else
    echo "--- ❌ Deployment FAILED ---"
    docker logs $CONTAINER_NAME
fi