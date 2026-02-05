import torch
import cv2
import subprocess
import threading
import time
import requests
import base64
import os
import re
from helpers import connect_camera

# --- 1. CONFIGURATION FROM DOCKER-COMPOSE ---
API_URL = "http://ollama-llm:11434/api/chat" 
MODEL_ID = "hf.co/JoseferEins/SmolVLM-500M-Instruct-fer0:latest"

# --- 2. CAMERA SETUP ---
cap = connect_camera()
out_w, out_h = 480, 360

# FFmpeg setup remains the same as your previous script 
out_stream_cmd = [
    'ffmpeg', '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo', '-pix_fmt', 'bgr24',
    '-s', f"{out_w}x{out_h}", '-r', '10', '-i', '-', '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p', '-preset', 'ultrafast', '-tune', 'zerolatency',
    '-f', 'mpegts', 'udp://127.0.0.1:55081?pkt_size=1316'
]
out_pipe = subprocess.Popen(out_stream_cmd, stdin=subprocess.PIPE)

# --- 3. SHARED STATE ---
last_ai_text = "Connecting to API..."
detection_box = None
current_frame_for_ai = None
new_frame_available = False

# --- 4. THE LIGHTWEIGHT AI WORKER ---
def ai_worker():
    global last_ai_text, current_frame_for_ai, new_frame_available, detection_box
    
    while True:
        if new_frame_available:
            try:
                frame_to_process = current_frame_for_ai.copy()
                new_frame_available = False 
                
                # Resize and Encode to Base64 for the REST API
                small_frame = cv2.resize(frame_to_process, (384, 384))
                _, buffer = cv2.imencode('.jpg', small_frame)
                img_b64 = base64.b64encode(buffer).decode('utf-8')
                
                # OpenAI-compatible payload used by OpenVINO/vLLM servers
                payload = {
                    "model": MODEL_ID,
                    "messages": [{
                        "role": "user",
                        "content": "Detect humans and return bounding boxes.",
                        "images": [img_b64] # Correct format for Ollama 
                    }],
                    "stream": False
                }
                                
                # Increase timeout for CPU-only processing
                response = requests.post(API_URL, json=payload, timeout=60)
                result = response.json()
                last_ai_text = result['message']['content']

                # Use your existing regex to find [ymin, xmin, ymax, xmax] 
                coords = re.findall(r"(\d+)", last_ai_text)
                detection_box = [int(c) for c in coords[:4]] if len(coords) >= 4 else None
                
            except Exception as e:
                last_ai_text = f"API Error: {str(e)[:20]}"
        else:
            time.sleep(0.05)

threading.Thread(target=ai_worker, daemon=True).start()

# --- 5. MAIN LOOP (THE "STREAMER") ---
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