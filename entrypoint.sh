#!/bin/bash
# entrypoint.sh

SCRIPT_NAME=$1
SLEEP_TIME=${2:-30}
# MODEL_ID is passed from docker-compose.yml
echo "--- VLM Startup: $SCRIPT_NAME ---"

# 1. Check if Model exists in the persistent volume
# We check if the 'models--...' folder exists in the HF cache
MODEL_CACHE_DIR="/root/.cache/huggingface/hub/models--$(echo $MODEL_ID | sed 's/\//--/g')"


if [ ! -z "$CAMERA_URL" ]; then
    echo "LOG: Using network camera stream: $CAMERA_URL"
elif [ -e "/dev/video0" ]; then
    echo "LOG: Using local hardware camera: /dev/video0"
    # (Optional: Add GID logic here if you ever move away from Docker Desktop)
else
    echo "WARNING: No camera source found."
fi

# Skip the download logic entirely if the directory exists
if [ -d "$MODEL_CACHE_DIR" ]; then
    echo "LOG: [$(date)] Model $MODEL_ID found. Skipping network check."
else
    echo "LOG: [$(date)] Model not found. Attempting download..."
    huggingface-cli download "$MODEL_ID" --quiet
fi

# --- DYNAMIC WEBCAM GROUP DETECTION ---
# Only runs if the device is visible (requires Native Docker)
if [ -e "/dev/video0" ]; then
    # Get the GID of /dev/video0 from the host
    VIDEO_GID=$(stat -c '%g' /dev/video0)
    echo "LOG: Detected host webcam GID: $VIDEO_GID"

    # Create a matching group inside the container if it doesn't exist
    if ! getent group hostvideo > /dev/null; then
        groupadd -g "$VIDEO_GID" hostvideo
        echo "LOG: Created group 'hostvideo' with GID $VIDEO_GID"
    fi

    # Add root to that group and ensure the device is readable
    usermod -a -G hostvideo root
    chmod 666 /dev/video0
    echo "LOG: Permissions synchronized for /dev/video0"
else
    echo "WARNING: /dev/video0 not found inside container."
    echo "If using Docker Desktop, this hardware path is blocked by the VM."
fi
# --- End of Dynamic Detection ---

# 2. Execution / Pending Loop
# Execution loop
# 2. Execution / Pending Loop
while true; do
    if [ -f "/app/scripts/$SCRIPT_NAME" ]; then
        echo "LOG: [$(date)] Checking for UDP traffic on port 55080..."
        
        # Use timeout with cat on the udp device - this is a bash-native way to check UDP
        # We try to read 1 byte. If it succeeds, traffic is present.
        if timeout 2s bash -c "exec 3<>/dev/udp/host.docker.internal/55080; cat <&3" > /dev/null 2>&1; then
             echo "LOG: [$(date)] Stream active. Starting $SCRIPT_NAME..."
             python3 "/app/scripts/$SCRIPT_NAME"
             sleep $SLEEP_TIME
        else
            # Fallback: if 'nc' worked for you manually, use it here
            if nc -zu -w 2 host.docker.internal 55080; then
                echo "LOG: [$(date)] Port 55080 is reachable. Starting $SCRIPT_NAME..."
                python3 "/app/scripts/$SCRIPT_NAME"
                sleep $SLEEP_TIME
            else
                echo "IDLE: No camera data. Waiting..."
                sleep 10
            fi
        fi
    fi
done