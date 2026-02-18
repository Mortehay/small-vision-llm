import cv2
import os
import time

# Directory inside the container (mapped to your host via volumes)
output_dir = "/app/logs/captured_frames"
os.makedirs(output_dir, exist_ok=True)

# Use the address you just verified
# 0.0.0.0 works if the traffic is being pushed TO this container
# stream_cam works if this script is PULLING from the other container
stream_url = "udp://0.0.0.0:55080?pkt_size=1316"

def process_stream():
    # Adding CAP_FFMPEG backend explicitly for stability
    cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
    
    # Set a small buffer to keep latency low for AI operations
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    print("Stream started. Press Ctrl+C to stop.")
    count = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Dropped frame or stream ended. Reconnecting...")
                continue
            
            # --- YOUR AI LOGIC HERE ---
            # Example: frame is a standard NumPy array
            # height, width = frame.shape[:2]
            
            # For testing: Print frame data every 30 frames
            if int(cap.get(cv2.CAP_PROP_POS_FRAMES)) % 30 == 0:
                print(f"Captured frame: {frame.shape}")
                count += 1
                try:
                    # Generate a filename with a timestamp or counter
                    filename = f"frame_{count:04d}.jpg"
                    filepath = os.path.join(output_dir, filename)

                    # Save the frame
                    # [Quality 90 is a good balance for AI and storage]
                    cv2.imwrite(filepath, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                    print(f"Saved: {filepath}")
                except Exception as e:
                    print(f"Error saving frame: {e}")
                

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        cap.release()

if __name__ == "__main__":
    process_stream()