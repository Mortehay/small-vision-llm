from flask import Flask, jsonify, send_from_directory, send_file
from flask_socketio import SocketIO
from flask_cors import CORS
import multiprocessing
import requests
import time
import sys
import os
import tailer
import shutil
import signal
import subprocess
import time
import threading
from datetime import datetime

import numpy as np
import cv2
import io

# Ensure the scripts directory is in the path so it can find camera_test
sys.path.append('/app/scripts')
from camera_test import run_analysis_loop

app = Flask(__name__)
CORS(app)
socketio = SocketIO(
    app,
    cors_allowed_origins="*"
)
worker_process = None
CAMERA_API = "http://stream-cam:5000"
# Define the image directory based on camera_test.py config
IMAGE_DIR = "/app/images/SmolVLM-500M-Instruct-fer0/captured_frames"
LOG_PATH = "/app/logs/SmolVLM-500M-Instruct-fer0/"

def signal_handler(sig, frame):
    """Cleanup function triggered on Ctrl+C"""
    print('\n[SYSTEM] Shutdown signal received. Cleaning up processes...')
    global worker_process
    
    # 1. Terminate the AI worker
    if worker_process and worker_process.is_alive():
        print("[SYSTEM] Terminating AI Worker...")
        worker_process.terminate()
        worker_process.join()
        
    # 2. Try to stop the remote camera if it's running
    try:
        requests.post(f"{CAMERA_API}/stop", timeout=2)
    except:
        pass
        
    print("[SYSTEM] Done. Exiting.")
    sys.exit(0)

# Register the listener
signal.signal(signal.SIGINT, signal_handler)

@app.route('/system/clear-history', methods=['POST'])
def clear_history():
    """Wipes all captured frames and log files."""
    try:
        # Clear Images
        if os.path.exists(IMAGE_DIR):
            for filename in os.listdir(IMAGE_DIR):
                file_path = os.path.join(IMAGE_DIR, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
        
        # Clear Logs (Optional: keep the current log file)
        if os.path.exists(LOG_PATH):
            for filename in os.listdir(LOG_PATH):
                if filename.endswith('.log'):
                    file_path = os.path.join(LOG_PATH, filename)
                    try:
                        os.unlink(file_path)
                    except:
                        pass # Current log might be in use
                        
        return jsonify({"status": "History cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/latest-frame')
def get_latest_frame():
    # 1. Try to find the actual latest frame
    try:
        log_files = [os.path.join(IMAGE_DIR, f) for f in os.listdir(IMAGE_DIR) if f.endswith('.jpg')]
        if log_files:
            latest_img = max(log_files, key=os.path.getmtime)
            return send_from_directory(IMAGE_DIR, os.path.basename(latest_img))
    except Exception:
        pass

    # 2. Fallback: Generate a local placeholder if no image exists
    # Create a 1280x720 dark gray image
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    img[:] = (30, 30, 35) # Slate-ish background
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    text = "Awaiting AI Frame..."
    cv2.putText(img, text, (400, 360), font, 1.5, (100, 100, 110), 3, cv2.LINE_AA)
    
    # Encode to memory and send
    _, buffer = cv2.imencode('.jpg', img)
    return send_file(io.BytesIO(buffer), mimetype='image/jpeg')

def log_reader_thread():
    """Background thread to emit logs via WebSocket without blocking."""
    current_file = None
    file_handle = None

    while True:
        try:
            # 1. Always look for the newest log file
            log_files = [os.path.join(LOG_PATH, f) for f in os.listdir(LOG_PATH) if f.endswith('.log')]
            if not log_files:
                time.sleep(1)
                continue
                
            latest_log = max(log_files, key=os.path.getmtime)

            # 2. If a new log file was created (e.g. after a restart), switch to it
            if latest_log != current_file:
                if file_handle: file_handle.close()
                current_file = latest_log
                file_handle = open(latest_log, 'r')
                file_handle.seek(0, 2) # Start at the end
                print(f"Log Reader now watching: {latest_log}")

            # 3. Read only new lines
            line = file_handle.readline()
            if line:
                # This triggers the "Saved AI Snapshot" check in React
                socketio.emit('log_update', {'data': line.strip()})
            else:
                time.sleep(0.1) # Prevent CPU spiking
        except Exception as e:
            time.sleep(1)


@app.route('/system/start', methods=['POST'])
def system_start():
    global worker_process
    
  

    # 2. Trigger the Hardware Camera (The 'Sending' side)
    try:
        requests.post("http://stream-cam:5000/start", timeout=5)

        time.sleep(5)

        # 1. Start AI Receiver (The 'Listening' side)
        if worker_process is None or not worker_process.is_alive():
            worker_process = multiprocessing.Process(target=run_analysis_loop)
            worker_process.start()
            
        # Give the AI script 1 second to open its UDP port
    
    except Exception as e:
        return jsonify({"error": f"Camera failed: {e}"}), 500

    return jsonify({"status": "System Online"}), 200

@app.route('/system/stop', methods=['POST'])
def system_stop():
    global worker_process
    
    # 1. Stop local AI processing
    if worker_process and worker_process.is_alive():
        worker_process.terminate()
        worker_process.join()
        worker_process = None
        
    # 2. Stop Remote Hardware
    try:
        requests.post(f"{CAMERA_API}/stop", timeout=5)
    except:
        pass
        
    return jsonify({"status": "System Offline"}), 200

@app.route('/system/status')
def system_status():
    timestamp = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    return {"status": "ok", "message": "Backend is reachable", "timestamp": timestamp}

# Start the log reader thread when the app starts

def start_background_threads():
    # Use SocketIO's helper to spawn the thread correctly
    socketio.start_background_task(target=log_reader_thread)

# Note: In Flask-SocketIO, we don't usually need a decorator for this 
# if we call it when the app starts, or use the first_request decorator.
@app.before_request
def initialize():
    # This ensures it only runs once
    if not hasattr(app, '_background_thread_started'):
        socketio.start_background_task(target=log_reader_thread)
        app._background_thread_started = True