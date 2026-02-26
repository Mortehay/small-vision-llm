import subprocess
import os
import time
import signal
from flask import Flask, jsonify

app = Flask(__name__)
process = None

# Destination is the internal container name of your operations container
UDP_DEST = "udp://stream_operations:55080?pkt_size=1316"

FFMPEG_CMD = [
    "ffmpeg", "-hide_banner", "-loglevel", "error",
    "-f", "v4l2", "-video_size", "640x480", "-i", "/dev/video0",
    "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
    "-pix_fmt", "yuv420p", 
    "-f", "mpegts", UDP_DEST
]

def kill_existing_ffmpeg():
    """Force kill any ffmpeg process holding the camera device."""
    try:
        subprocess.run(["pkill", "-9", "ffmpeg"], check=False)
        time.sleep(1) # Wait for kernel to release /dev/video0
    except:
        pass

@app.route('/start', methods=['POST'])
def start_stream():
    global process
    
    # Always attempt a clean start by killing ghosts
    kill_existing_ffmpeg()
    
    try:
        log_file = open("/tmp/ffmpeg_debug.log", "w")
        process = subprocess.Popen(
            FFMPEG_CMD,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setpgrp
        )
        
        # Verify the process didn't immediately crash
        time.sleep(1.5)
        if process.poll() is not None:
            return jsonify({"error": "FFmpeg failed to initialize camera. Check /tmp/ffmpeg_debug.log"}), 500
            
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
    app.run(host='0.0.0.0', port=5000)