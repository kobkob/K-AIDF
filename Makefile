#!/usr/bin/env make

.PHONY: all install clean

# Default target
all: install

# Install Ollama and OLMo in Docker
install: docker-check ollama-install olmo-install cli-route polar-integration mcp-setup

# Check Docker availability
docker-check:
	@if ! command -v docker &> /dev/null; then \
		echo "Error: Docker is not installed. Please install Docker first."; \
		exit 1; \
	fi

# Install Ollama
ollama-install:
	@echo "Installing Ollama..."; \
	docker run -d --name ollama -v ollama:/root/.ollama -p 11434:11434 --privileged ollama/ollama

# Install OLMo model
olmo-install:
	@echo "Pulling OLMo model..."; \
	docker exec ollama ollama pull olmo

# CLI default routing to OLMo
cli-route:
	@echo "Configuring CLI to default to OLMo..."; \
	# Remove legacy command prefixes and route to OLMo
	sed -i 's|/mentor/||g; s|/init/||g' scripts/cli-entrypoint.sh
	echo 'export DEFAULT_MODEL="olmo"' >> scripts/cli-entrypoint.sh

# Polar.sh payment integration
polar-integration:
	@echo "Setting up Polar.sh payment webhook..."; \
	curl -X POST https://api.polar.sh/webhooks -H "Content-Type: application/json" \
	-d '{"event":"payment_success","callback_url":"https://kobkob.app/install"}'

# MCP server setup
mcp-setup:
	@echo "Initializing MCP local server..."; \
	mkdir -p mcp-server && \
	cd mcp-server && \
	curl -sSL https://github.com/kobkob/mcp/releases/latest/download/mcp-server | tar -xz && \
	./mcp-server --config config.yaml

# Cleanup
clean:
	rm -rf ollama mcp-server scripts/cli-entrypoint.sh.bak