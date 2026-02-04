import torch
import cv2
import subprocess
import threading
import time
import logging
import os
import re
from datetime import datetime
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageTextToText
from helpers import connect_camera

# Force CPU to use all cores for math operations
os.environ["OMP_NUM_THREADS"] = "8"
os.environ["MKL_NUM_THREADS"] = "8"
# Set this to the number of physical cores you want to dedicate
torch.set_num_threads(8) 
# Optimization for faster CPU operations
torch.set_num_interop_threads(8)

# --- 1. DIRECTORY & LOGGING SETUP ---
log_dir = '/app/logs'
# Force the directory to exist inside the container's view
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

current_date = datetime.now().strftime("%Y_%m_%d")
log_path = os.path.join(log_dir, f"smol_vlm_app_{current_date}.log")

# This will now succeed because we forced the directory creation above
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(log_path), logging.StreamHandler()]
)
logger = logging.getLogger("SmolVLM")

# --- 2. MODEL SETUP ---
MODEL_ID = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
DEVICE = "cpu" # Explicitly CPU for ThinkBook stability

logger.info(f"Loading model on {DEVICE}...")
processor = AutoProcessor.from_pretrained(MODEL_ID)
model = AutoModelForImageTextToText.from_pretrained(
    MODEL_ID, 
    torch_dtype=torch.bfloat16,
    _attn_implementation="eager"
).to(DEVICE)

FRAME_RESOLUTION = os.getenv("FRAME_RESOLUTION", "640x480")
FRAME_RESOLUTION_CROPED = os.getenv("FRAME_RESOLUTION_CROPED", "480x360")

# --- 3. CAMERA & PIPE SETUP ---
cap = connect_camera()
# Get the actual dimensions from the camera to ensure FFmpeg matches
ret, first_frame = cap.read()
if not ret:
    raise Exception("Could not read initial frame from camera")
h, w, _ = first_frame.shape
actual_res = f"{w}x{h}"

out_stream_cmd = [
    'ffmpeg', 
    '-y',
    '-f', 'rawvideo', 
    '-vcodec', 'rawvideo', 
    '-pix_fmt', 'bgr24',       # OpenCV default
    '-s', actual_res,          # MUST match the frame.tobytes() size
    '-r', '10', 
    '-i', '-', 
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',     # Standard for video players
    '-preset', 'ultrafast', 
    '-tune', 'zerolatency', 
    '-f', 'mpegts',
    'udp://127.0.0.1:55081?pkt_size=1316'
]
out_pipe = subprocess.Popen(out_stream_cmd, stdin=subprocess.PIPE)

# --- 4. SHARED VARIABLES ---
last_ai_text = "Searching..."
detection_box = None
current_frame_for_ai = None
new_frame_available = False

# --- 5. AI WORKER (THE "THINKER") ---
def ai_worker():
    global last_ai_text, current_frame_for_ai, new_frame_available, detection_box
    logger.info("AI Thread active.")
    
    while True:
        # If the main loop has provided a frame
        if new_frame_available:
            try:
                # Capture the frame and tell the main loop we are BUSY
                # This prevents 'if new_frame_available' from being True constantly
                frame_to_process = current_frame_for_ai.copy()
                new_frame_available = False 
                
                # Small size for speed
                small_frame = cv2.resize(frame_to_process, (320, 240))
                image = Image.fromarray(cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB))
                
                logger.info("AI starting inference on a new frame...")
                
                messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "Detect humans."}]}]
                prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
                inputs = processor(text=prompt, images=[image], return_tensors="pt").to(DEVICE)
                
                generated_ids = model.generate(
                    **inputs, 
                    max_new_tokens=10,        # Reduce from 40 to 10 for testing
                    do_sample=False,          # Faster than sampling
                    use_cache=True            # Speeds up generation
                )
                result = processor.batch_decode(generated_ids, skip_special_tokens=True)
                
                last_ai_text = result[0].split('assistant')[-1].strip()
                logger.info(f"AI LOG: {last_ai_text}") # This will fill your logs!

                coords = re.findall(r"(\d+)", last_ai_text)
                detection_box = [int(c) for c in coords[:4]] if len(coords) >= 4 else None
                
            except Exception as e:
                logger.error(f"AI ERROR: {e}")
        else:
            time.sleep(0.01) # Short sleep to prevent CPU spiking while idle

threading.Thread(target=ai_worker, daemon=True).start()

# --- 6. MAIN LOOP (THE "STREAMER") ---
frame_count = 0
# Define desired output resolution explicitly to match FFmpeg -s
out_w, out_h = 480, 360
while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break
    # FORCE RESIZE to match the FFmpeg pipe resolution
    # This prevents the horizontal "shifted" stripes
    frame = cv2.resize(frame, (out_w, out_h))

    frame_count += 1

    # Only pass every 10th frame to AI thread
    if frame_count % 30 == 0 and not new_frame_available:
        current_frame_for_ai = frame.copy()
        new_frame_available = True

    # Draw UI on every frame
    h, w, _ = frame.shape
    if detection_box:
        ymin, xmin, ymax, xmax = detection_box
        start = (int(xmin * w / 1000), int(ymin * h / 1000))
        end = (int(xmax * w / 1000), int(ymax * h / 1000))
        cv2.rectangle(frame, start, end, (0, 0, 255), 3)

    cv2.rectangle(frame, (10, 10), (w-10, 60), (0,0,0), -1)
    cv2.putText(frame, f"AI: {last_ai_text}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

    # Write the correctly sized frame to the pipe
    out_pipe.stdin.write(frame.tobytes())

cap.release()