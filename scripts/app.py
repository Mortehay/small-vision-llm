from gevent import monkey
monkey.patch_all()

import sqlite3
import uuid
import os
import sys
import subprocess
import time
import requests
import signal
import threading
from datetime import datetime
import numpy as np
import cv2
import io

from flask import Flask, jsonify, send_from_directory, send_file, request
from flask_socketio import SocketIO
from flask_cors import CORS

DB_PATH = "/data/streams.db"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS streams (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                url TEXT NOT NULL,
                type TEXT NOT NULL,
                username TEXT,
                password TEXT
            )
        ''')
        # Seed default streams if table is empty
        cursor = conn.execute('SELECT COUNT(*) FROM streams')
        if cursor.fetchone()[0] == 0:
            # 1. First Option: Local Webcam
            conn.execute('INSERT INTO streams (id, name, display_name, url, type, username, password) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        ("local", "local_webcam", "Local Webcam", "/dev/video0", "local", "", ""))
            
            # 2. ESP32-CAM (Initial seed uses env variables if provided)
            user_env = os.environ.get("WEB_USER", "")
            pass_env = os.environ.get("WEB_PASS", "")
            
            conn.execute('INSERT INTO streams (id, name, display_name, url, type, username, password) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        ("esp32", "esp32_cam", "ESP32-CAM", "https://192.168.0.195/stream", "external", user_env, pass_env))
        
        # Migrations/Updates for existing data
        conn.execute("UPDATE streams SET url = REPLACE(url, '/view', '/stream') WHERE url LIKE '%/view'")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Global to track current active stream config
active_stream_config = None

app = Flask(__name__)
CORS(app)
socketio = SocketIO(
    app,
    cors_allowed_origins="*"
)
worker_process = None
CAMERA_API = "http://stream-cam:5000"

# Base directories
BASE_IMAGE_DIR = "/data/images"
BASE_LOG_PATH = "/data/logs"
HLS_BASE_DIR = "/data/logs/HLS_STREAMS"

def get_current_paths():
    global active_stream_config
    name = active_stream_config['name'] if active_stream_config else "default"
    image_dir = f"{BASE_IMAGE_DIR}/{name}/captured_frames"
    log_path = f"{BASE_LOG_PATH}/{name}/"
    return image_dir, log_path

@app.route('/streams', methods=['GET'])
def get_streams():
    with get_db_connection() as conn:
        # Order by a CASE statement to ensure 'local' is always first
        query = '''
            SELECT * FROM streams 
            ORDER BY (CASE WHEN id = 'local' THEN 0 ELSE 1 END), display_name ASC
        '''
        streams = [dict(row) for row in conn.execute(query).fetchall()]
    return jsonify(streams)

@app.route('/streams', methods=['POST'])
def add_stream():
    data = request.json
    stream_id = str(uuid.uuid4())
    name = data.get('name', 'new_stream').replace(' ', '_').lower()
    display_name = data.get('display_name', 'New Stream')
    url = data.get('url', '')
    stream_type = data.get('type', 'external')
    username = data.get('username', '')
    password = data.get('password', '')
    
    with get_db_connection() as conn:
        conn.execute('INSERT INTO streams (id, name, display_name, url, type, username, password) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (stream_id, name, display_name, url, stream_type, username, password))
    
    return jsonify({"id": stream_id, "name": name, "display_name": display_name}), 201

@app.route('/streams/<stream_id>', methods=['PUT'])
def update_stream(stream_id):
    data = request.json
    with get_db_connection() as conn:
        conn.execute('''
            UPDATE streams 
            SET name = ?, display_name = ?, url = ?, type = ?, username = ?, password = ?
            WHERE id = ?
        ''', (
            data.get('name', '').replace(' ', '_').lower(),
            data.get('display_name', ''),
            data.get('url', ''),
            data.get('type', ''),
            data.get('username', ''),
            data.get('password', ''),
            stream_id
        ))
    return jsonify({"status": "updated"})

@app.route('/streams/<stream_id>', methods=['DELETE'])
def delete_stream(stream_id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM streams WHERE id = ?', (stream_id,))
    return jsonify({"status": "deleted"})

@app.route('/hls-streams/<path:filename>')
def serve_hls(filename):
    """Serve HLS manifest and segments with correct CORS and cache headers."""
    response = send_from_directory(HLS_BASE_DIR, filename)
    
    # Fix MIME types for HLS segments (Flask/Python might guess .ts as TypeScript or Qt)
    if filename.endswith('.ts'):
        response.headers['Content-Type'] = 'video/mp2t'
    elif filename.endswith('.m3u8'):
        response.headers['Content-Type'] = 'application/vnd.apple.mpegurl'

    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

def signal_handler(sig, frame):
    """Cleanup function triggered on Ctrl+C"""
    print('\n[SYSTEM] Shutdown signal received. Cleaning up processes...')
    global worker_process
    
    # 1. Terminate the AI worker
    if worker_process and worker_process.poll() is None:
        print("[SYSTEM] Terminating AI Worker...")
        worker_process.terminate()
        try:
            worker_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            worker_process.kill()
        
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
    """Wipes all captured frames and log files for the current stream."""
    try:
        image_dir, log_path = get_current_paths()
        # Clear Images
        if os.path.exists(image_dir):
            for filename in os.listdir(image_dir):
                file_path = os.path.join(image_dir, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
        
        # Clear Logs (Optional: keep the current log file)
        if os.path.exists(log_path):
            for filename in os.listdir(log_path):
                if filename.endswith('.log'):
                    file_path = os.path.join(log_path, filename)
                    try:
                        os.unlink(file_path)
                    except:
                        pass # Current log might be in use
                        
        return jsonify({"status": "History cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/latest-frame')
def get_latest_frame():
    image_dir, _ = get_current_paths()
    # 1. Try to find the actual latest frame
    try:
        if os.path.exists(image_dir):
            log_files = [os.path.join(image_dir, f) for f in os.listdir(image_dir) if f.endswith('.jpg')]
            if log_files:
                latest_img = max(log_files, key=os.path.getmtime)
                return send_from_directory(image_dir, os.path.basename(latest_img))
    except Exception:
        pass

    # 2. Fallback: Generate a local placeholder if no image exists
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    img[:] = (30, 30, 35) # Slate-ish background
    font = cv2.FONT_HERSHEY_SIMPLEX
    text = "Awaiting AI Frame..."
    cv2.putText(img, text, (400, 360), font, 1.5, (100, 100, 110), 3, cv2.LINE_AA)
    
    # Encode to memory and send
    _, buffer = cv2.imencode('.jpg', img)
    return send_file(io.BytesIO(buffer), mimetype='image/jpeg')

@app.route('/latest-frame-fallback')
def get_latest_frame_fallback():
    # 1. Fallback: Generate a local placeholder if no image exists
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    img[:] = (30, 30, 35) # Slate-ish background
    timestamp = datetime.now().strftime("%H:%M:%S")
    font = cv2.FONT_HERSHEY_SIMPLEX
    text = f"Awaiting Frame... {timestamp}"
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
            _, log_path = get_current_paths()
            # 1. Always look for the newest log file
            if not os.path.exists(log_path):
                time.sleep(1)
                continue
                
            log_files = [os.path.join(log_path, f) for f in os.listdir(log_path) if f.endswith('.log')]

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
    global worker_process, active_stream_config
    
    data = request.json or {}
    stream_id = data.get('stream_id', 'local')
    
    # Load and find the stream config from DB
    with get_db_connection() as conn:
        row = conn.execute('SELECT * FROM streams WHERE id = ?', (stream_id,)).fetchone()
        if not row:
            row = conn.execute('SELECT * FROM streams LIMIT 1').fetchone()
        active_stream_config = dict(row)
    
    # Stop existing if any
    system_stop()
    
    # 1. Start AI Receiver
    if worker_process is None or worker_process.poll() is not None:
        cmd = [sys.executable, "/app/scripts/camera_test.py"]
        env = os.environ.copy()
        env["STREAM_NAME"] = active_stream_config['name']
        
        print(f"[SYSTEM] Starting AI Worker for stream {active_stream_config['name']}")
        try:
            worker_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                start_new_session=True
            )
            print(f"[SYSTEM] AI Worker started with PID: {worker_process.pid}")
        except Exception as e:
            print(f"[SYSTEM] Failed to start AI Worker: {e}")
            return jsonify({"error": f"Failed to start AI Worker: {str(e)}"}), 500
    
    # 2. Robust Camera Trigger (with retries)
    max_retries = 5
    for i in range(max_retries):
        try:
            cam_resp = requests.post(f"{CAMERA_API}/start", json=active_stream_config, timeout=5)
            if cam_resp.status_code != 200:
                 return jsonify({"error": f"Camera service error: {cam_resp.text}"}), 500
            return jsonify({"status": "System Online", "stream": active_stream_config}), 200
        except requests.exceptions.ConnectionError:
            if i < max_retries - 1:
                time.sleep(2)
                continue
            return jsonify({"error": "Camera service not reachable"}), 500

@app.route('/system/stop', methods=['POST'])
def system_stop():
    global worker_process
    
    # 1. Stop local AI processing
    if worker_process and worker_process.poll() is None:
        print("[SYSTEM] Stopping AI Worker...")
        worker_process.terminate()
        try:
            worker_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            worker_process.kill()
        worker_process = None
        
    # 2. Stop Remote Hardware
    try:
        requests.post(f"{CAMERA_API}/stop", timeout=5)
    except:
        pass
        
    return jsonify({"status": "System Offline"}), 200

@app.route('/system/status')
def system_status():
    global worker_process, active_stream_config
    worker_alive = False
    if worker_process is not None:
        worker_alive = worker_process.poll() is None
    
    timestamp = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    return {
        "status": "ok", 
        "worker_alive": worker_alive,
        "active_stream": active_stream_config,
        "message": f"AI Worker is active ({active_stream_config['name'] if active_stream_config else 'None'})" if worker_alive else "AI Worker is stopped", 
        "timestamp": timestamp
    }

@app.before_request
def initialize():
    global active_stream_config
    if not hasattr(app, '_db_initialized'):
        init_db()
        app._db_initialized = True
        if active_stream_config is None:
            with get_db_connection() as conn:
                row = conn.execute('SELECT * FROM streams WHERE id = ?', ('local',)).fetchone()
                if not row:
                    row = conn.execute('SELECT * FROM streams LIMIT 1').fetchone()
                if row: active_stream_config = dict(row)
                    
    if not hasattr(app, '_background_thread_started'):
        socketio.start_background_task(target=log_reader_thread)
        app._background_thread_started = True