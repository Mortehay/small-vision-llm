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
LLM_NAME = "SmolVLM-500M-Instruct-fer0"
INPUT_URL = "udp://0.0.0.0:55080?pkt_size=1316"
OUTPUT_URL = "udp://172.17.0.1:55081?pkt_size=1316"
API_URL = "http://ollama-llm:11434/api/chat"
MODEL_ID = f"hf.co/JoseferEins/{LLM_NAME}:latest"
IMAGE_DIR = f"/data/images/{LLM_NAME}/captured_frames"
LOG_DIR = f"/data/logs/{LLM_NAME}" # FIX 2: Ensure LOG_DIR is defined

# --- LOGGING SETUP ---
# --- camera_test.py ---

def get_logger():
    # Use an absolute path for reliability
    abs_log_dir = "/data/logs/SmolVLM-500M-Instruct-fer0"
    os.makedirs(abs_log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d") # Group by day
    log_filename = os.path.join(abs_log_dir, f"ai_debug_{timestamp}.log")

    logger = logging.getLogger("AI_Worker")
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
    if os.path.exists(IMAGE_DIR):
        try:
            shutil.rmtree(IMAGE_DIR)
            logger.info(f"Cleared image directory: {IMAGE_DIR}")
        except Exception as e:
            logger.error(f"Failed to clear images: {e}")
    os.makedirs(IMAGE_DIR, exist_ok=True)
    
    # 2. Preserve Logs: We only ensure the directory exists.
    # We remove the code that was unlinking files in LOG_DIR.
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)
    else:
        logger.info(f"Log directory preserved: {LOG_DIR}")

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
    logger.info(f"run_analysis_loop started. Using INPUT_URL: {INPUT_URL}")
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "probesize;5000000|analyzeduration;5000000"
    
    # --- 1. SETUP INPUT ---
    logger.info("Opening VideoCapture...")
    cap = cv2.VideoCapture(INPUT_URL, cv2.CAP_FFMPEG)
    
    if not cap.isOpened():
        logger.error(f"Could not open video stream: {INPUT_URL}. Check if FFmpeg is sending data.")
        return
    logger.info("VideoCapture opened successfully.")

    # 2. DISCARD initial "broken" frames until we hit a Keyframe
    logger.info("Syncing with camera stream (reading first few frames)...")
    for i in range(30): # Try for up to 30 frames
        logger.info(f"Attempting to read sync frame {i}...")
        ret, frame = cap.read()
        if ret and frame is not None:
            logger.info(f"Sync successful on frame {i}!")
            break
        logger.warning(f"Failed to read sync frame {i}")
        time.sleep(0.5)
    


    # --- 2. SETUP OUTPUT STREAM (FFMPEG PIPE) ---
    # resolution must match the input (640x480)
    actual_res = "640x480" 
    out_stream_cmd = [
        'ffmpeg', '-y',
        '-loglevel', 'error',
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgr24', '-s', '640x480', '-r', '30', 
        '-i', '-', 
        '-c:v', 'libx264', 
        '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast', 
        '-tune', 'zerolatency',
        '-g', '30',                         # Force keyframe every 30 frames
        '-bsf:v', 'dump_extra',             # Extract and insert SPS/PPS from extradata
        '-flags', '+global_header',         # Ensure headers are present
        '-f', 'mpegts', OUTPUT_URL
    ]
    
    # Start the output process
    out_pipe = subprocess.Popen(
        out_stream_cmd, 
        stdin=subprocess.PIPE,
        bufsize=10**7  # ~10MB buffer to prevent blocking
    )
    
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

            # --- 3. PUSH TO OUTPUT STREAM ---
            # We send every frame to the output stream for smooth playback
            try:
                #this log spams all file
                #logger.info(f"Pushing frame to output stream {out_pipe.stdin}")
                out_pipe.stdin.write(frame.tobytes())
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
        if out_pipe.stdin:
            out_pipe.stdin.close()
        out_pipe.terminate()
        try:
            out_pipe.wait(timeout=0.5) # Give it a moment to exit cleanly
        except subprocess.TimeoutExpired:
            out_pipe.kill() # Force kill if it doesn't close
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
    