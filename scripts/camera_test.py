import cv2
import os
import subprocess
import shutil
import base64
import requests
import re
import time
import sys
import threading
import logging
from datetime import datetime
import socket
import signal

# --- CONFIGURATION ---
STREAM_NAME = os.environ.get("STREAM_NAME", "default")
LLM_NAME = "SmolVLM-500M-Instruct-fer0" # Keeping model name but prefixing paths with stream name
INPUT_URL = "udp://0.0.0.0:55080"
OUTPUT_URL = "udp://172.17.0.1:55081?pkt_size=1316"
API_URL = "http://ollama-llm:11434/api/chat"
MODEL_ID = f"hf.co/JoseferEins/{LLM_NAME}:latest"

# Unique paths per stream
IMAGE_DIR = f"/data/images/{STREAM_NAME}/captured_frames"
LOG_DIR = f"/data/logs/{STREAM_NAME}"
STREAM_DIR = "/data/logs/HLS_STREAMS"
RAW_STREAM_DIR = os.path.join(STREAM_DIR, "raw")
PROC_STREAM_DIR = os.path.join(STREAM_DIR, "processed")

# --- LOGGING SETUP ---

def get_logger():
    # Use an absolute path for reliability
    os.makedirs(LOG_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d") # Group by day
    log_filename = os.path.join(LOG_DIR, f"ai_debug_{timestamp}.log")

    logger = logging.getLogger(f"AI_Worker_{STREAM_NAME}")
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers to prevent duplicate logs
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    # Console Handler
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.INFO)
    c_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

    # File Handler
    f_handler = logging.FileHandler(log_filename, mode='a', delay=False)
    f_handler.setLevel(logging.INFO)
    f_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    f_handler.setFormatter(f_format)
    logger.addHandler(f_handler)

    return logger

# Initialize logger
logger = get_logger()


def test_udp_network(url, timeout=5):
    try:
        # Extract port 55080 from the URL
        port = int(url.split(":")[2].split("?")[0])
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", port))
        sock.settimeout(timeout)
        
        logger.info(f"TESTING NETWORK: Listening on port {port}...")
        data, addr = sock.recvfrom(1024)
        logger.info(f"NETWORK SUCCESS: Received {len(data)} bytes from {addr}")
        sock.close()
        return True
    except Exception as e:
        logger.error(f"NETWORK FAILURE: No data received on port {port}. Error: {e}")
        return False

# Global state
state = {
    "current_frame": None,
    "new_frame_available": False,
    "detection_box": None,
    "running": True
}

def setup_dirs():
    """Clears existing images but keeps logs to preserve startup history."""
    # 1. Clear Images: Completely wipe and recreate the image directory
    os.makedirs(IMAGE_DIR, exist_ok=True)
    
    # 2. Setup Stream Dirs
    for d in [RAW_STREAM_DIR, PROC_STREAM_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
        # Ensure web server can read (dist/ might be owned by root in container)
        try:
            os.chmod(d, 0o755)
        except:
            pass

    # 3. Preserve Logs...

def save_and_clean_frame(frame, saved_count):
    try:
        # Re-scan to see current actual files
        files = [os.path.join(IMAGE_DIR, f) for f in os.listdir(IMAGE_DIR) if f.endswith('.jpg')]
        files.sort(key=os.path.getmtime)

        # Strictly keep only 9 oldest so we can add the 10th
        if len(files) >= 10:
            for i in range(len(files) - 9):
                os.remove(files[i])

        # Save the new 10th image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Tip: Use a modulo on saved_count to keep names repeating 0-9 if you prefer
        filename = f"frame_{saved_count % 10:01d}_{timestamp}.jpg" 
        cv2.imwrite(os.path.join(IMAGE_DIR, filename), frame)
        
        # Flush stdout so the log reader sees it immediately
        sys.stdout.flush() 
        return True
    except Exception as e:
        print(f"Cleanup Error: {e}")
        return False

def run_analysis_loop():
    global state
    setup_dirs()
    # Standard LISTEN_URL for OpenCV inside Docker
    LISTEN_URL = "udp://0.0.0.0:55080"
    logger.info(f"run_analysis_loop starting. Listening on: {LISTEN_URL}")
    
    # Increase probing to ensure H.264/MJPEG recognition
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "probesize;5000000|analyzeduration;5000000"
    
    # --- 1. SETUP INPUT WITH RETRIES ---
    logger.info("Opening VideoCapture (with retries)...")
    cap = None
    max_init_retries = 30 # Even more retries
    for attempt in range(max_init_retries):
        cap = cv2.VideoCapture(LISTEN_URL, cv2.CAP_FFMPEG)
        if cap.isOpened():
            logger.info(f"VideoCapture opened successfully on attempt {attempt + 1}.")
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            break
        
        logger.warning(f"Attempt {attempt + 1}: Could not open stream. Waiting for FFmpeg...")
        if cap: cap.release()
        time.sleep(3)
    
    if cap is None or not cap.isOpened():
        logger.error(f"FATAL: Could not open stream {LISTEN_URL} after {max_init_retries} attempts.")
        return

    # 2. SYNC WITH STREAM (Discard early broken frames)
    logger.info("Syncing with stream...")
    # Read up to 200 frames to find a valid keyframe from the webcam
    for i in range(200): 
        ret, frame = cap.read()
        if ret and frame is not None:
            logger.info(f"Stream sync successful on frame {i}!")
            break
        if i % 20 == 0:
            logger.warning(f"Searching for valid frames... (attempt {i})")
        time.sleep(0.01)
    


    # --- 2. SETUP HLS OUTPUT STREAMS ---
    def start_hls_pipe(output_path, input_url=None):
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
        ]
        if input_url:
            cmd += ['-i', input_url]
        else:
            cmd += [
                '-f', 'rawvideo', '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24', '-s', '640x480', '-r', '30', '-i', '-'
            ]
            
        cmd += [
            '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
            '-g', '30', '-hls_time', '2', '-hls_list_size', '3', '-hls_flags', 'delete_segments',
            '-f', 'hls', os.path.join(output_path, "live.m3u8")
        ]
        return subprocess.Popen(cmd, stdin=subprocess.PIPE if not input_url else None)

    # Raw stream pipe
    raw_hls = start_hls_pipe(RAW_STREAM_DIR)
    # Processed stream from Pipe
    proc_hls = start_hls_pipe(PROC_STREAM_DIR)
    
    # Keeping old UDP output for compatibility if still needed
    udp_out_cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgr24', '-s', '640x480', '-r', '30', 
        '-i', '-', 
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast', '-tune', 'zerolatency',
        '-g', '30', '-f', 'mpegts', OUTPUT_URL
    ]
    udp_out_pipe = subprocess.Popen(udp_out_cmd, stdin=subprocess.PIPE, bufsize=10**7)
    
    frame_count = 0
    saved_count = 0

    logger.info(f"Analysis Loop started. Input: {INPUT_URL} | Output: {OUTPUT_URL}")

    try:
        logger.info(f"Starting while loop")
        while state["running"]:
            ret, frame = cap.read()
            #logger.info(f"Frame received {ret}")
            if not ret:
                logger.warning("Empty frame received. Waiting...")
                time.sleep(1)
                continue

            # --- 3. PUSH TO OUTPUT STREAMS ---
            try:
                frame_bytes = frame.tobytes()
                udp_out_pipe.stdin.write(frame_bytes)
                raw_hls.stdin.write(frame_bytes)
                proc_hls.stdin.write(frame_bytes)
            except Exception as pipe_err:
                logger.error(f"Pipe error: {pipe_err}")

            # --- 4. SAMPLING FOR AI ---
            if frame_count % 30 == 0:
                
                if save_and_clean_frame(frame, saved_count):
                    logger.info(f"Saved AI Snapshot: frame {saved_count}")
                    sys.stdout.flush()
                    saved_count += 1

            frame_count += 1
            
    except Exception as e:
        logger.error(f"Error in analysis loop: {e}")
    finally:
        cap.release()
        for p in [udp_out_pipe, proc_hls, raw_hls]:
            if p.stdin:
                p.stdin.close()
            p.terminate()
            try:
                p.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                p.kill()
        logger.info("Stream connections closed.")

if __name__ == "__main__":
    # Signal handling for SIGTERM
    def handle_sigterm(signum, frame):
        logger.info("SIGTERM received, stopping...")
        state["running"] = False
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    # Ensure the directories exist
    setup_dirs()
    # Run the main analysis loop
    try:
        run_analysis_loop()
    except KeyboardInterrupt:
        logger.info("Analysis loop stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        sys.exit(1)
    