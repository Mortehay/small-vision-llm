# Management Commands
COMPOSE=docker compose

# Camera Streaming
CAMERA_URL=http://127.0.0.1:55080?listen=1


.PHONY: build up stop force-retry update-llm

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d


up-smol:
	$(COMPOSE) up -d smol-vlm

up-moon:
	$(COMPOSE) up -d moondream

up-qwen:
	$(COMPOSE) up -d qwen-vl

rebuild:
	$(COMPOSE) down
	$(COMPOSE) build
	$(COMPOSE) up -d


rebuild-clean:
	$(COMPOSE) down --remove-orphans
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

logs:
	$(COMPOSE) logs -f

stop:
	$(COMPOSE) stop

# Force a specific container to restart (re-triggers the entrypoint)
# Usage: make force-retry target=smol-vlm
force-retry:
	@if [ -z "$(target)" ]; then \
		echo "Error: Specify target, e.g., 'make force-retry target=smol-vlm'"; \
	else \
		$(COMPOSE) restart $(target); \
	fi

# Check and update the LLM weights inside the running container
update-llm:
	@if [ -z "$(target)" ]; then \
		echo "Error: Specify target, e.g., 'make update-llm target=vlm_smol'"; \
	else \
		docker exec -it $(target) python3 -c "from transformers import AutoModel; AutoModel.from_pretrained(model_id, force_download=True)" \
	fi

update-models:
	@echo "Checking for LLM updates via HuggingFace CLI..."
	docker exec -it vlm_smol huggingface-cli download HuggingFaceTB/SmolVLM2-500M-Video-Instruct
	docker exec -it vlm_moondream huggingface-cli download vikhyatk/moondream2
	docker exec -it vlm_qwen huggingface-cli download Qwen/Qwen2-VL-2B-Instruct

check-cam:
	@echo "--- 1. Host Check ---"
	ls -l /dev/video0
	@echo "--- 2. Docker VM Check ---"
	# If this fails, Docker Desktop's VM is isolating the hardware
	docker run --rm -v /dev:/dev alpine ls -l /dev/video0
	@echo "--- 3. Permission Check ---"
	getent group video || echo "No video group found on host"
### to view ffplay -fflags nobuffer -flags low_delay udp://127.0.0.1:55080
###  sudo apt install ffmpeg
# stream-cam:
# 	ffmpeg -fflags nobuffer -flags low_delay \
# 	       -f v4l2 -framerate 10 -video_size 1280x720 -i /dev/video0 \
# 	       -vcodec libx264 -preset ultrafast -tune zerolatency \
# 	       -x264-params repeat-headers=1:keyint=20 \
# 	       -f mpegts "udp://0.0.0.0:55080?pkt_size=1316"
# stream-cam:
# 	ffmpeg -fflags nobuffer -flags low_delay \
#            -f v4l2 -framerate 10 -video_size 1280x720 -i /dev/video0 \
#            -vcodec libx264 -preset ultrafast -tune zerolatency \
#            -x264-params repeat-headers=1:keyint=10 \
#            -f mpegts "udp://192.168.65.2:55080?pkt_size=1316&buffer_size=65535"
# stream-cam:
# 	ffmpeg -fflags nobuffer -flags low_delay \
#            -f v4l2 -framerate 10 -video_size 1280x720 -i /dev/video0 \
#            -vcodec libx264 -preset ultrafast -tune zerolatency \
#            -x264-params repeat-headers=1:keyint=10 \
#            -f mpegts "udp://172.17.0.1:55080?pkt_size=1316"

stream-cam:
	docker exec -it stream-cam ffmpeg -fflags nobuffer -flags low_delay \
           -f v4l2 -framerate 10 -video_size 1280x720 -i /dev/video0 \
           -vcodec libx264 -preset ultrafast -tune zerolatency \
           -x264-params repeat-headers=1:keyint=10 \
           -f mpegts "udp://192.168.65.2:55080?pkt_size=1316&buffer_size=65535"

# Use this to check if the container can actually "see" the host
test-net:
	docker exec -it vlm_smol ping -c 3 host.docker.internal

# Open an interactive shell in a container
# Usage: make shell name=vlm_smol
shell:
	@if [ -z "$(name)" ]; then \
		echo "Error: Specify container name, e.g., 'make shell name=vlm_smol'"; \
	else \
		docker exec -it $(name) /bin/bash; \
	fi