FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg procps && rm -rf /var/lib/apt/lists/*
RUN pip install flask flask-cors flask-socketio
WORKDIR /app
COPY scripts/camera_control.py .
CMD ["python", "camera_control.py"]