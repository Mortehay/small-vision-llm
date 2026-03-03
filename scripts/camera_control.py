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
    "ffmpeg", "-hide_banner", 
    "-f", "v4l2", 
    "-input_format", "yuyv422", 
    "-video_size", "640x480", 
    "-i", "/dev/video0",
    "-c:v", "libx264", 
    "-preset", "ultrafast", 
    "-tune", "zerolatency",
    "-g", "15",                     # Lower GOP size (Keyframe every 15 frames)
    "-x264-params", "keyint=15:min-keyint=15:scenecut=0", # Force consistent keyframes
    "-flags", "+global_header", 
    "-bsf:v", "dump_extra",         # Extracts and inserts extra data (SPS/PPS)
    "-pix_fmt", "yuv420p", 
    "-f", "mpegts", 
    UDP_DEST
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
    kill_existing_ffmpeg()
    
    try:
        # Use line buffering (buffering=1) so logs appear immediately
        log_file = open("/tmp/ffmpeg_debug.log", "w", buffering=1)
        process = subprocess.Popen(
            FFMPEG_CMD,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setpgrp,
            universal_newlines=True # Helps with text-based logging
        )
        
        time.sleep(2.0) # Increased wait time
        if process.poll() is not None:
            return jsonify({"error": "FFmpeg exited immediately"}), 500
            
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