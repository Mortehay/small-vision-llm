from flask import Flask, jsonify, send_from_directory
import multiprocessing
import requests
import time
import sys
from flask_socketio import SocketIO
from flask_cors import CORS
import os
import tailer
import shutil
# Ensure the scripts directory is in the path so it can find camera_test
sys.path.append('/app/scripts')
from camera_test import run_analysis_loop

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
worker_process = None
CAMERA_API = "http://stream-cam:5000"
# Define the image directory based on camera_test.py config
IMAGE_DIR = "/app/images/SmolVLM-500M-Instruct-fer0/captured_frames"
LOG_PATH = "/app/logs/SmolVLM-500M-Instruct-fer0/"


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
    """Serves the most recent 30th-frame capture."""
    try:
        files = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.jpg')]
        if not files:
            return jsonify({"error": "No frames found"}), 404
        latest_file = max([os.path.join(IMAGE_DIR, f) for f in files], key=os.path.getctime)
        return send_from_directory(IMAGE_DIR, os.path.basename(latest_file))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def log_reader_thread():
    """Background thread to emit logs via WebSocket."""
    # Find the latest log file created by get_logger()
    while True:
        try:
            log_files = [os.path.join(LOG_PATH, f) for f in os.listdir(LOG_PATH) if f.endswith('.log')]
            if log_files:
                latest_log = max(log_files, key=os.path.getctime)
                for line in tailer.follow(open(latest_log)):
                    socketio.emit('log_update', {'data': line})
            time.sleep(1)
        except:
            time.sleep(2)

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
    return {"status": "ok", "message": "Backend is reachable"}

# Start the log reader thread when the app starts
import threading
threading.Thread(target=log_reader_thread, daemon=True).start()

if __name__ == '__main__':
    # Add the allow_unsafe_werkzeug flag here
    socketio.run(app, host='0.0.0.0', port=5001, allow_unsafe_werkzeug=True)