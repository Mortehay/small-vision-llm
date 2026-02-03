# Use a slim Python 3.10 image
FROM python:3.10-slim

# Install modern system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    v4l-utils \
    git \
    tcpdump \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-specific PyTorch (much smaller for your Ryzen 5)
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install VLM libraries
RUN pip3 install --no-cache-dir \
    transformers \
    accelerate \
    opencv-python-headless \
    pillow \
    timm \
    qwen-vl-utils \
    num2words

WORKDIR /app

# Ensure entrypoint is ready
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh