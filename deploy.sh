#!/bin/bash

# Configuration
CONTAINER_NAME="informacast_dash"
IMAGE_NAME="informacast_dash"

echo "--- 🛠️  Starting Deployment ---"

# 1. GitHub Sync
echo "Step 1: Syncing with GitHub..."
git add .

# Ask for a commit message
echo "Enter your commit message (what did you change?):"
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

# --no-cache ensures the container doesn't use old versions of your code
docker build --no-cache -t $IMAGE_NAME .

echo "Step 3: Starting Container..."
docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  -p 5082:5082 \
  $IMAGE_NAME

echo "--- ✅ Deployment Complete! ---"
docker logs --tail 10 $CONTAINER_NAME

