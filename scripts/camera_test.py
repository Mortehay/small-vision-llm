import cv2
import os
import subprocess
import shutil
import base64
import requests
import re
import time
import threading
import logging
from datetime import datetime
import socket

# --- CONFIGURATION ---
LLM_NAME = "SmolVLM-500M-Instruct-fer0"
INPUT_URL = "udp://0.0.0.0:55080?pkt_size=1316"
OUTPUT_URL = "udp://172.17.0.1:55081?pkt_size=1316"
API_URL = "http://ollama-llm:11434/api/chat"
MODEL_ID = f"hf.co/JoseferEins/{LLM_NAME}:latest"
IMAGE_DIR = f"/app/images/{LLM_NAME}/captured_frames"
LOG_DIR = f"/app/logs/{LLM_NAME}" # FIX 2: Ensure LOG_DIR is defined

# --- LOGGING SETUP ---
def get_logger():
    # Ensure directory exists before trying to write a file
    os.makedirs(LOG_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H")
    log_filename = f"{LOG_DIR}/ai_debug_{timestamp}.log"
    

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_filename) 
        ]
    )
    return logging.getLogger("AI_Worker")

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

# Initialize logger immediately
logger = get_logger()

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
  

def run_analysis_loop():
    global state
    setup_dirs()
    logger.info(f"run_analysis_loop started")
    # --- 1. SETUP INPUT ---
    cap = cv2.VideoCapture(INPUT_URL, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        logger.error("Could not open video stream. Check if FFmpeg is sending data.")
        return

    # --- 2. SETUP OUTPUT STREAM (FFMPEG PIPE) ---
    # resolution must match the input (640x480)
    actual_res = "640x480" 
    out_stream_cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgr24', '-s', actual_res, '-r', '30', 
        '-i', '-',  # Read from stdin pipe
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast', '-tune', 'zerolatency',
        '-f', 'mpegts', OUTPUT_URL
    ]
    
    # Start the output process
    out_pipe = subprocess.Popen(out_stream_cmd, stdin=subprocess.PIPE)
    
    frame_count = 0
    saved_count = 0

    logger.info(f"Analysis Loop started. Input: {INPUT_URL} | Output: {OUTPUT_URL}")

    try:
        logger.info(f"Starting while loop")
        while state["running"]:
            ret, frame = cap.read()
            logger.info(f"Frame received {ret}")
            if not ret:
                logger.warning("Empty frame received. Waiting...")
                time.sleep(1)
                continue

            # --- 3. PUSH TO OUTPUT STREAM ---
            # We send every frame to the output stream for smooth playback
            try:
                logger.info(f"Pushing frame to output stream {out_pipe.stdin}")
                out_pipe.stdin.write(frame.tobytes())
            except Exception as pipe_err:
                logger.error(f"Pipe error: {pipe_err}")

            # --- 4. SAMPLING FOR AI ---
            if frame_count % 30 == 0:
                logger.info(f"Sampling frame {frame_count}")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"frame_{saved_count:04d}_{timestamp}.jpg"
                filepath = os.path.join(IMAGE_DIR, filename)
                
                cv2.imwrite(filepath, frame)
                
                state["current_frame"] = frame
                state["new_frame_available"] = True
                
                logger.info(f"Saved AI Snapshot: {filename} {filepath}")
                saved_count += 1

            frame_count += 1
            
    except Exception as e:
        logger.error(f"Error in analysis loop: {e}")
    finally:
        cap.release()
        out_pipe.stdin.close()
        out_pipe.terminate()
        logger.info("Stream connections closed.")
    