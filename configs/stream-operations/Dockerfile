# Use a slim Python 3.12 image
FROM python:3.12-slim

# Install system dependencies (Adding curl to fetch Node.js)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    v4l-utils \
    git \
    tcpdump \
    netcat-openbsd \
    ffmpeg \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first
COPY configs/stream-operations/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy everything (including your frontend folder)
COPY . .

# Start the Flask API
ENTRYPOINT ["python", "scripts/app.py"]