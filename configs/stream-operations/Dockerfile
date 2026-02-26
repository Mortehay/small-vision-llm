# Use a slim Python 3.12 image
FROM python:3.12-slim

# Install system dependencies for OpenCV and FFmpeg
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    v4l-utils \
    git \
    tcpdump \
    netcat-openbsd \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY configs/stream-operations/requirements.txt ./requirements.txt

# Install CPU-specific PyTorch (remains separate due to custom index URL)
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install all other dependencies from the file
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of your scripts
COPY . .

# Start the Flask API
ENTRYPOINT ["python", "scripts/app.py"]