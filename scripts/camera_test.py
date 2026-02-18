import cv2
import os
import subprocess
import shutil
import glob

# --- CONFIGURATION ---
input_url = "udp://0.0.0.0:55080?pkt_size=1316&buffer_size=10000000&fifo_size=500000"
output_url = "udp://host.docker.internal:55081?pkt_size=1316"
output_dir = "/app/logs/captured_frames"
MAX_IMAGES = 20

def setup_directory(path):
    """Empties the directory if it exists, otherwise creates it."""
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    print(f"Directory {path} cleaned and ready.")

def maintain_limit(path, limit):
    """Deletes the oldest files if the count exceeds the limit."""
    # Get list of files sorted by creation time
    files = sorted(glob.glob(os.path.join(path, "*.jpg")), key=os.path.getctime)
    
    while len(files) >= limit:
        oldest_file = files.pop(0)
        try:
            os.remove(oldest_file)
        except Exception as e:
            print(f"Error deleting {oldest_file}: {e}")

def process_and_restream():
    # 1. Start Fresh
    setup_directory(output_dir)

    # 2. Setup Input
    cap = cv2.VideoCapture(input_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)

    # 3. Setup Output Stream (FFmpeg Pipe)
    ffmpeg_cmd = [
        'ffmpeg',
        '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', '640x480', '-pix_fmt', 'bgr24', '-r', '30',
        '-i', '-', 
        '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
        '-f', 'mpegts', output_url
    ]
    out_pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    print(f"Processing started. Reading from 55080, Streaming to 55081...")

    count = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            # 4. Save JPG and Maintain Limit (Every 30th frame)
            if count % 30 == 0:
                # Clean up oldest before saving new
                maintain_limit(output_dir, MAX_IMAGES)
                
                filepath = os.path.join(output_dir, f"frame_{time.time():.0f}.jpg")
                cv2.imwrite(filepath, frame)
                print(f"Saved: {filepath} (Total in dir: {len(glob.glob(os.path.join(output_dir, '*.jpg')))})")

            # 5. Push frame to output stream
            out_pipe.stdin.write(frame.tobytes())
            count += 1

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        cap.release()
        out_pipe.stdin.close()
        out_pipe.terminate()

if __name__ == "__main__":
    import time # Needed for timestamp filenames
    process_and_restream()