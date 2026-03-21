SHELL := /usr/bin/env bash

.PHONY: help env-agent env-mcp test-generator test-agent test-mcp test-all \
	generate-default generate-maturity generate-ethical agent-shell agent-packs \
	mcp-up mcp-down mcp-logs

help:
	@echo "K-AIDF workspace automation"
	@echo ""
	@echo "make test-generator   Run generator tests"
	@echo "make test-agent       Run agent tests"
	@echo "make test-mcp         Run MCP tests"
	@echo "make test-all         Run all test targets"
	@echo "make generate-default Generate the default K-AIDF repository"
	@echo "make generate-maturity Generate the maturity-model pack example"
	@echo "make generate-ethical Generate the ethical-model pack example"
	@echo "make env-agent        Print/export agent environment summary"
	@echo "make env-mcp          Print/export MCP environment summary"
	@echo "make agent-shell      Launch the terminal agent shell"
	@echo "make agent-packs      List doctrine packs through agent-aidf"
	@echo "make mcp-up           Start the MCP stack with Docker Compose"
	@echo "make mcp-down         Stop the MCP stack"
	@echo "make mcp-logs         Tail MCP logs"

env-agent:
	@source ./scripts/load-agent-env.sh

env-mcp:
	@source ./scripts/load-mcp-env.sh

test-generator:
	@cd kobkob-kaidf-generator && PYTHONPATH=src python -m pytest -q

test-agent:
	@cd agent-aidf && PYTHONPATH=src python -m pytest -q

test-mcp:
	@cd mcp-aidf && python -m unittest discover -s tests -p 'test_*.py' && python -m py_compile app.py

test-all: test-generator test-agent test-mcp

generate-default:
	@cd kobkob-kaidf-generator && bash scripts/dev.sh

generate-maturity:
	@cd kobkob-kaidf-generator && bash scripts/generate-maturity-pack-example.sh

generate-ethical:
	@cd kobkob-kaidf-generator && bash scripts/generate-ethical-pack-example.sh

agent-shell:
	@source ./scripts/load-agent-env.sh && cd agent-aidf && PYTHONPATH=src python -m agent_aidf.cli --repo "$$AIDF_REPO_ROOT" shell

agent-packs:
	@source ./scripts/load-agent-env.sh && cd agent-aidf && PYTHONPATH=src python -m agent_aidf.cli --repo "$$AIDF_REPO_ROOT" packs

mcp-up:
	@source ./scripts/load-mcp-env.sh && cd mcp-aidf && docker compose up --build -d

mcp-down:
	@source ./scripts/load-mcp-env.sh && cd mcp-aidf && docker compose down

mcp-logs:
	@source ./scripts/load-mcp-env.sh && cd mcp-aidf && docker compose logs -f
