from flask import Flask, jsonify
import multiprocessing
import requests
import time
import sys
# Ensure the scripts directory is in the path so it can find camera_test
sys.path.append('/app/scripts')
from camera_test import run_analysis_loop

app = Flask(__name__)
worker_process = None
CAMERA_API = "http://stream-cam:5000"

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

if __name__ == '__main__':
    # Running on 6000 to avoid conflict with camera-cam on 5000
    app.run(host='0.0.0.0', port=6000)