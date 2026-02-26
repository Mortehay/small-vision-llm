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
from datetime import datetime  # CRITICAL: Fixes the NameError

# --- CONFIGURATION ---
LLM_NAME = "SmolVLM-500M-Instruct-fer0"
INPUT_URL = "udp://0.0.0.0:55080?pkt_size=1316"
OUTPUT_URL = "udp://172.17.0.1:55081?pkt_size=1316"
API_URL = "http://ollama-llm:11434/api/chat"
MODEL_ID = f"hf.co/JoseferEins/{LLM_NAME}:latest"
IMAGE_DIR = f"/app/images/{LLM_NAME}/captured_frames"
LOG_DIR = f"/app/logs/{LLM_NAME}"  # Directory for log files

# --- LOGGING SETUP ---
def get_logger():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)
    
    # Create unique log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{LOG_DIR}/ai_debug_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_filename)  # Re-enables the log file
        ]
    )
    return logging.getLogger("AI_Worker")

logger = get_logger()

# Global state
state = {
    "current_frame": None,
    "new_frame_available": False,
    "detection_box": None,
    "running": True
}

def setup_dirs():
    """Wipe old images, but keep old logs."""
    if os.path.exists(IMAGE_DIR):
        shutil.rmtree(IMAGE_DIR)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)

def ai_worker():
    """Background thread for LLM inference"""
    logger.info("AI Worker Thread started.")
    while state["running"]:
        if state["new_frame_available"] and state["current_frame"] is not None:
            try:
                # 1. Save "Before" Image
                ts = int(time.time())
                frame = state["current_frame"].copy()
                cv2.imwrite(f"{IMAGE_DIR}/frame_{ts}_before.jpg", frame)
                
                state["new_frame_available"] = False 
                
                logger.info(f"Frame {ts}: Sending to AI...")
                
                # Inference payload
                small_frame = cv2.resize(frame, (224, 224))
                _, buffer = cv2.imencode('.jpg', small_frame)
                img_b64 = base64.b64encode(buffer).decode('utf-8')
                
                payload = {
                    "model": MODEL_ID,
                    "messages": [{"role": "user", "content": "Provide face bounding box [ymin, xmin, ymax, xmax]", "images": [img_b64]}],
                    "stream": False,
                    "options": {"temperature": 0, "num_predict": 30, "num_thread": 4}
                }
                
                response = requests.post(API_URL, json=payload, timeout=60)
                res_text = response.json().get('message', {}).get('content', '')
                
                nums = re.findall(r"(\d+\.\d+|\d+)", res_text)
                if len(nums) >= 4:
                    vals = [float(n) for n in nums[:4]]
                    h, w = 480, 640
                    div = 1.0 if all(0 <= v <= 1 for v in vals) else 1000.0
                    state["detection_box"] = [int(vals[0]*h/div), int(vals[1]*w/div), int(vals[2]*h/div), int(vals[3]*w/div)]
                    
                    # 2. Save "After" Image
                    y1, x1, y2, x2 = state["detection_box"]
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.imwrite(f"{IMAGE_DIR}/frame_{ts}_after.jpg", frame)
                    logger.info(f"AI Success: Box saved for frame {ts}")
                else:
                    logger.warning(f"AI returned no box: {res_text}")
                    
            except Exception as e:
                logger.error(f"AI Thread Error: {e}")
        time.sleep(0.1)

def run_analysis_loop():
    setup_dirs()
    state["running"] = True
    frame_count = 0
    
    threading.Thread(target=ai_worker, daemon=True).start()
    cap = cv2.VideoCapture(INPUT_URL, cv2.CAP_FFMPEG)
    
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', '640x480', '-pix_fmt', 'bgr24', '-r', '30', '-i', '-', 
        '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
        '-f', 'mpegts', OUTPUT_URL
    ]
    out_pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    try:
        while state["running"]:
            ret, frame = cap.read()
            if not ret:
                continue

            frame_count += 1

            # Trigger AI every 30 frames
            if frame_count % 30 == 0:
                if not state["new_frame_available"]:
                    state["current_frame"] = frame.copy()
                    state["new_frame_available"] = True
                    logger.info(f"Frame {frame_count}: Triggering AI analysis.")

            # Live Overlay
            if state["detection_box"]:
                y1, x1, y2, x2 = state["detection_box"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            try:
                out_pipe.stdin.write(frame.tobytes())
            except:
                break
    finally:
        state["running"] = False
        cap.release()
        out_pipe.terminate()