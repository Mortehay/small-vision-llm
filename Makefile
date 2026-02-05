ifneq ("$(wildcard .env)","")
    include .env
    export $(shell sed 's/=.*//' .env)
endif
LLM_LIST := $(shell echo $(LLM_LIST) | sed 's/"//g')

# Management Commands
COMPOSE=docker compose

# Camera Streaming
CAMERA_URL=http://127.0.0.1:55080?listen=1
# Variables
COMPOSE_FILE=docker-compose.yml
CONTAINER_NAME=ollama-llm
SETUP_CONTAINER=ollama-setup


BOOTSTRAP_SCRIPT=./run-ollama.sh

.PHONY: help up down restart logs status shell pull-models clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start all containers with auto-detected GPU IDs
	@chmod +x $(BOOTSTRAP_SCRIPT)
	@$(BOOTSTRAP_SCRIPT)
	@echo "Local AI services (Ollama & Stable Diffusion) are starting..."

down: ## Stop and remove all containers
	docker compose down

restart: ## Restart all containers
	docker compose restart

status: ## Show status of containers
	docker compose ps

rebuild: ## Rebuild and start containers with auto-detected GPU IDs
	docker compose down --remove-orphans
	@chmod +x $(BOOTSTRAP_SCRIPT)
	@./$(BOOTSTRAP_SCRIPT) --build
	@echo "Rebuild complete."
	
logs: ## Follow logs of the Ollama container
	docker logs -f $(CONTAINER_NAME)

sd-logs: ## Follow Stable Diffusion logs (essential for monitoring torch installation)
	docker logs -f $(SD_CONTAINER)

sd-shell: ## Enter the Stable Diffusion container
	docker exec -it $(SD_CONTAINER) /bin/bash

setup-logs: ## Check the progress of model downloads
	docker logs -f $(SETUP_CONTAINER)

shell: ## Enter the Ollama container shell
	docker exec -it $(CONTAINER_NAME) /bin/bash

pull-models: ## Pull specific models from Hugging Face
	docker exec -i -e HF_TOKEN=$(HF_TOKEN) $(CONTAINER_NAME) ollama pull hf.co/JoseferEins/SmolVLM-500M-Instruct-fer0;\
	docker exec -i -e HF_TOKEN=$(HF_TOKEN) $(CONTAINER_NAME) ollama pull hf.co/sugiv/cardvaultplus-500m-gguf:Q4_K_M;\
	docker exec -i -e HF_TOKEN=$(HF_TOKEN) $(CONTAINER_NAME) ollama pull hf.co/Mungert/LightOnOCR-1B-1025-GGUF:Q3_K_S;\
	docker exec -i -e HF_TOKEN=$(HF_TOKEN) $(CONTAINER_NAME) ollama pull hf.co/aipib/LightOnOCR-1B-1025-ft-ja1-Q4_K_M-GGUF:Q4_K_M;\
	docker exec -i -e HF_TOKEN=$(HF_TOKEN) $(CONTAINER_NAME) ollama pull hf.co/prithivMLmods/LightOnOCR-1B-1025-AIO-GGUF:Q8_0;\
	docker exec -i -e HF_TOKEN=$(HF_TOKEN) $(CONTAINER_NAME) ollama pull hf.co/mradermacher/Qwen2-VL-2B-Abliterated-Caption-it-i1-GGUF:IQ1_M;
	

clean: ## Remove containers and prune unused volumes (CAUTION: deletes models)
	docker compose down -v

check-models: ## List models currently loaded in the container
	@curl -s http://localhost:11435/api/tags | jq -r '.models[].name'



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

reset-cam:
	sudo modprobe -r uvcvideo
	sudo modprobe uvcvideo

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