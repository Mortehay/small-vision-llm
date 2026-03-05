import subprocess
import os
import time
import signal
from flask import Flask, jsonify, request

app = Flask(__name__)
process = None

# Destination is the internal container name of your operations container
UDP_DEST = "udp://stream_operations:55080?pkt_size=1316"

def kill_existing_ffmpeg():
    """Force kill any ffmpeg process holding the camera device."""
    try:
        subprocess.run(["pkill", "-9", "ffmpeg"], check=False)
        time.sleep(1) # Wait for kernel to release device
    except:
        pass

@app.route('/start', methods=['POST'])
def start_stream():
    global process
    kill_existing_ffmpeg()
    
    data = request.json or {}
    stream_type = data.get('type', 'local')
    url = data.get('url', '/dev/video0')
    username = data.get('username', '')
    password = data.get('password', '')

    cmd = ["ffmpeg", "-hide_banner"]
    
    if stream_type == 'local':
        cmd += [
            "-f", "v4l2",
            "-input_format", "yuyv422",
            "-framerate", "30", # Explicit framerate for local devices
            "-video_size", "640x480",
            "-i", url
        ]
    else:
        # For external streams like ESP32-CAM (MJPEG over HTTPS)
        headers = ""
        if username and password:
            import base64
            auth = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers = f"Authorization: Basic {auth}\r\n"
        
        # Robustness for external MJPEG streams
        cmd += [
            "-hwaccel", "auto",
            "-fflags", "nobuffer+genpts",
            "-flags", "low_delay",
            "-strict", "experimental",
        ]
        
        if headers:
            cmd += ["-headers", headers]
            
        cmd += [
            "-probesize", "5000000",
            "-analyzeduration", "5000000",
            "-user_agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "-f", "mjpeg", 
            "-i", url
        ]
    
    # Common encoding for both types
    cmd += [
        "-c:v", "libx264", 
        "-preset", "ultrafast", 
        "-tune", "zerolatency",
        "-g", "15",
        "-x264-params", "keyint=15:min-keyint=15:scenecut=0",
        "-flags", "+global_header", 
        "-bsf:v", "dump_extra",
        "-pix_fmt", "yuv420p", 
        "-f", "mpegts", 
        UDP_DEST
    ]
    
    try:
        log_file = open("/tmp/ffmpeg_debug.log", "w", buffering=1)
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setpgrp,
            universal_newlines=True
        )
        
        time.sleep(2.0)
        if process.poll() is not None:
            return jsonify({"error": "FFmpeg exited immediately", "cmd": " ".join(cmd)}), 500
            
        return jsonify({"status": "Stream started", "pid": process.pid}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/stop', methods=['POST'])
def stop_stream():
    global process
    kill_existing_ffmpeg()
    process = None
    return jsonify({"status": "Stopped"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)