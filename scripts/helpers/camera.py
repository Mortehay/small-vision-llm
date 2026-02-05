import cv2
import time
import os

camera_src = os.getenv("CAMERA_URL", "udp://host.docker.internal:55080")

def connect_camera():
    # Start with the bare essentials
    src = "udp://host.docker.internal:55080"
    
    while True:
        print(f"LOG: Attempting to open {src}...")
        cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG) 
        
        if cap.isOpened():
            print("LOG: Camera connected!")
            return cap
            
        print(f"WAITING: Stream timeout at {src}. Check 'docker logs stream-cam'")
        cap.release() 
        time.sleep(2)