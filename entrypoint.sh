#!/bin/bash
# entrypoint.sh

SCRIPT_NAME=$1

echo "--- VLM Container Started ---"
echo "Target script: $SCRIPT_NAME"

while true; do
    if [ -f "/app/scripts/$SCRIPT_NAME" ]; then
        echo "Found $SCRIPT_NAME. Attempting to start LLM..."
        # Execute the script and capture the exit code
        python3 "/app/scripts/$SCRIPT_NAME"
        EXIT_CODE=$?
        
        echo "Process exited with code $EXIT_CODE."
        echo "Retrying in 30 seconds... (Press Ctrl+C in terminal to stop container)"
    else
        echo "LOG: [$(date)] File /app/scripts/$SCRIPT_NAME not found. Waiting..."
    fi
    
    # Sleep 30 seconds before retrying
    sleep 30
done