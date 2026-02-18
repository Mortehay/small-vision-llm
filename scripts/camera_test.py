import cv2
import os
import subprocess

# --- CONFIGURATION ---
input_url = "udp://0.0.0.0:55080?pkt_size=1316&buffer_size=10000000&fifo_size=500000"
output_url = "udp://host.docker.internal:55081?pkt_size=1316"
output_dir = "/app/logs/captured_frames"
os.makedirs(output_dir, exist_ok=True)

def process_and_restream():
    # 1. Setup Input
    cap = cv2.VideoCapture(input_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 3) # Internal OpenCV buffer

    # 2. Setup Output Stream (FFmpeg Pipe)
    # This takes raw frames from Python and streams them out via UDP
    ffmpeg_cmd = [
        'ffmpeg',
        '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', '640x480', '-pix_fmt', 'bgr24', '-r', '30',
        '-i', '-', # Input from pipe
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

            # --- OPTIONAL: DRAW ON FRAME (AI Visuals) ---
            # cv2.putText(frame, "AI ACTIVE", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # 3. Save JPG (Every 30th frame)
            if count % 30 == 0:
                filepath = os.path.join(output_dir, f"frame_{count//30:04d}.jpg")
                cv2.imwrite(filepath, frame)
                print(f"Saved JPG: {filepath}")

            # 4. Push frame to output stream
            out_pipe.stdin.write(frame.tobytes())
            count += 1

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        cap.release()
        out_pipe.stdin.close()
        out_pipe.terminate()

if __name__ == "__main__":
    process_and_restream()