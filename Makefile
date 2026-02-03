# Management Commands
COMPOSE=docker compose

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