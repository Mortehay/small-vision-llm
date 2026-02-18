import cv2
import os
import subprocess
import shutil
import glob
import base64
import requests
import re
import time
import threading
import logging
from datetime import datetime

# --- LOGGING SETUP ---
# Generate timestamp for the log filename
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"/app/logs/ai_debug_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_filename)
    ]
)
logger = logging.getLogger("AI_Worker")

# --- CONFIGURATION ---
INPUT_URL = "udp://0.0.0.0:55080?pkt_size=1316&buffer_size=10000000&fifo_size=500000"
OUTPUT_URL = "udp://host.docker.internal:55081?pkt_size=1316"
API_URL = "http://ollama-llm:11434/api/chat"
MODEL_ID = "hf.co/JoseferEins/SmolVLM-500M-Instruct-fer0:latest"

LOG_DIR = "/app/logs/captured_frames"
AI_LOG_DIR = "/app/logs/captured_frames_smol_llm"
MAX_IMAGES = 20

# --- SHARED STATE ---
current_frame_for_ai = None
new_frame_available = False
detection_box = None # [ymin, xmin, ymax, xmax]
last_ai_text = "Initializing..."

def setup_dirs():
    for d in [LOG_DIR, AI_LOG_DIR]:
        if os.path.exists(d):
            logger.info(f"Cleaning directory: {d}")
            shutil.rmtree(d)
        os.makedirs(d)

def maintain_limit(path, limit):
    """Deletes oldest files if folder exceeds limit."""
    files = sorted(glob.glob(os.path.join(path, "*.jpg")), key=os.path.getctime)
    while len(files) >= limit:
        deleted = files.pop(0)
        os.remove(deleted)

def ai_worker():
    global last_ai_text, current_frame_for_ai, new_frame_available, detection_box
    logger.info("AI Worker (CPU Optimized) started.")
    
    while True:
        if new_frame_available and current_frame_for_ai is not None:
            try:
                frame_to_process = current_frame_for_ai.copy()
                new_frame_available = False 
                
                # REDUCE SIZE: 224x224 is standard for many CPU vision models
                # This makes the base64 string smaller and the math faster
                small_frame = cv2.resize(frame_to_process, (224, 224))
                _, buffer = cv2.imencode('.jpg', small_frame)
                img_b64 = base64.b64encode(buffer).decode('utf-8')
                
                payload = {
                    "model": MODEL_ID,
                    "messages": [
                        {
                            "role": "user", 
                            # Simplest possible detection prompt for VLM
                            "content": "Can you provide the bounding box for the face in this image? Respond with [ymin, xmin, ymax, xmax]", 
                            "images": [img_b64]
                        }
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "num_predict": 30, # Small limit to prevent essays
                        "num_thread": 4,  # Adjust to your CPU cores
                        "num_ctx": 1024
                    }
                }
                
                logger.info("Requesting CPU Inference...")
                response = requests.post(API_URL, json=payload, timeout=120)
                response.raise_for_status()
                
                last_ai_text = response.json().get('message', {}).get('content', '').strip()
                logger.info(f"AI Output: {last_ai_text}")

                # Improved Regex: Catch numbers in brackets or plain text
                # Looks for integers or decimals
                nums = re.findall(r"(\d+\.\d+|\d+)", last_ai_text)
                
                if len(nums) >= 4:
                    # Convert found strings to floats
                    vals = [float(n) for n in nums[:4]]
                    h, w = 480, 640
                    
                    # Normalize if the model gives us 0-1 values
                    if all(0 <= v <= 1 for v in vals):
                        ymin, xmin, ymax, xmax = vals
                        detection_box = [int(ymin*h), int(xmin*w), int(ymax*h), int(xmax*w)]
                    # Normalize if the model gives us 0-1000 values
                    else:
                        ymin, xmin, ymax, xmax = vals
                        detection_box = [int(ymin*h/1000), int(xmin*w/1000), int(ymax*h/1000), int(xmax*w/1000)]
                    
                    logger.info(f"Final Box: {detection_box}")
                else:
                    detection_box = None
                    logger.warning("No coordinates found. Model returned text/markdown.")

            except Exception as e:
                logger.error(f"Worker Error: {e}")
                time.sleep(5) # Wait longer on error to let CPU cool down
        else:
            time.sleep(0.5) # Don't check too often on CPU

def main():
    global current_frame_for_ai, new_frame_available, detection_box
    setup_dirs()
    
    # Start AI Thread
    threading.Thread(target=ai_worker, daemon=True).start()

    cap = cv2.VideoCapture(INPUT_URL, cv2.CAP_FFMPEG)
    
    # Restreaming pipe
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', '640x480', '-pix_fmt', 'bgr24', '-r', '30', '-i', '-', 
        '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
        '-f', 'mpegts', OUTPUT_URL
    ]
    out_pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    count = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret: continue

            if not new_frame_available:
                current_frame_for_ai = frame.copy()
                new_frame_available = True

            # Visualize detection
            if detection_box:
                y1, x1, y2, x2 = detection_box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, "HUMAN", (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Status line
            cv2.putText(frame, f"Log: {os.path.basename(log_filename)}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Periodic raw logging
            if count % 60 == 0:
                maintain_limit(LOG_DIR, MAX_IMAGES)
                cv2.imwrite(os.path.join(LOG_DIR, f"raw_{int(time.time())}.jpg"), frame)

            out_pipe.stdin.write(frame.tobytes())
            count += 1

    except KeyboardInterrupt:
        logger.info("Exiting...")
    finally:
        cap.release()
        out_pipe.terminate()

if __name__ == "__main__":
    main()