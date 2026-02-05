#!/bin/bash

# Function to get a safe GID for a specific group name
get_safe_gid() {
    local group_name=$1
    local preferred_id=$2
    
    # 1. Use the actual GID if the group exists on host
    local actual_id=$(getent group "$group_name" | cut -d: -f3)
    if [ -n "$actual_id" ]; then
        echo "$actual_id"
    else
        # 2. Check if preferred ID is occupied by a DIFFERENT group
        local occupied=$(getent group "$preferred_id")
        if [ -z "$occupied" ]; then
            echo "$preferred_id"
        else
            # 3. Occupied! Find max system GID and add 1
            local max_gid=$(getent group | cut -d: -f3 | sort -n | tail -1)
            echo $((max_gid + 1))
        fi
    fi
}

# Detect or Calculate safe IDs
export RENDER_GID=$(get_safe_gid "render" 992)
export VIDEO_GID=$(get_safe_gid "video" 44)

# Ensure they aren't the same (Docker Compose requirement)
if [ "$RENDER_GID" == "$VIDEO_GID" ]; then
    VIDEO_GID=$((RENDER_GID + 1))
fi

echo "--- GPU Permission Setup ---"
echo "Target Render GID: $RENDER_GID"
echo "Target Video GID: $VIDEO_GID"
echo "----------------------------"

# Check if the shared network exists, create if not
NETWORK_NAME="shared-ai-network"
if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
    echo "Creating network: $NETWORK_NAME"
    docker network create "$NETWORK_NAME"
else
    echo "Network $NETWORK_NAME already exists."
fi


docker compose up -d "$@"

echo "Ollama is starting. You can check GPU logs with: docker logs -f ollama"