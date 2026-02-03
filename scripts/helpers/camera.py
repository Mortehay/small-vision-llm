import cv2
import time
import os

camera_src = "udp://172.17.0.1:55080"

def connect_camera():
    # Use the Docker internal DNS name which resolves to your host bridge
    # Adding 'reuse=1' prevents the "Address already in use" error
    src = f"{camera_src}?fifo_size=500000&reuse=1&serv=0" 
    
    while True:
        # Force the FFmpeg backend for UDP streams
        cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG) 
        
        if cap.isOpened():
            print("LOG: Camera connected!")
            return cap
            
        print(f"ERROR: Cannot open {camera_src}. Retrying in 5s...")
        cap.release() 
        time.sleep(5)