# K-AIDF/Makefile

SHELL := /usr/bin/env bash

export ANSWER
export PROMPT

.PHONY: help env-agent env-mcp test-generator test-agent test-mcp test-all \
	install-agent install-generator install-mcp ensure-generated-repo generate-default generate-maturity generate-ethical agent-shell agent-packs \
	agent-status agent-context agent-mentor agent-mentor-status agent-mentor-reset \
	agent-apps agent-app-run agent-app-runtime agent-app-stop \
	mcp-up mcp-down mcp-logs \
        workspace-up workspace-down

help:
	@echo "K-AIDF workspace automation"
	@echo ""
	@echo "make test-generator   Run generator tests"
	@echo "make test-agent       Run agent tests"
	@echo "make test-mcp         Run MCP tests"
	@echo "make test-all         Run all test targets"
	@echo "make install-generator Create/update the generator virtualenv and install dependencies"
	@echo "make install-agent    Create/update the agent virtualenv and install dependencies"
	@echo "make install-mcp      Create/update the MCP virtualenv and install dependencies"
	@echo "make ensure-generated-repo Generate the default K-AIDF repo if the expected path is missing"
	@echo "make generate-default Generate the default K-AIDF repository"
	@echo "make generate-maturity Generate the maturity-model pack example"
	@echo "make generate-ethical Generate the ethical-model pack example"
	@echo "make env-agent        Print/export agent environment summary"
	@echo "make env-mcp          Print/export MCP environment summary"
	@echo "make agent-shell      Launch the terminal agent shell"
	@echo "make agent-status     Show current agent project/runtime status"
	@echo "make agent-context    Show current agent context"
	@echo "make agent-mentor     Continue the mentor workflow (pass ANSWER='...')"
	@echo "make agent-mentor-status Show persisted mentor workflow state"
	@echo "make agent-mentor-reset Reset persisted mentor workflow state"
	@echo "make agent-packs      List doctrine packs through agent-aidf"
	@echo "make agent-apps       List persistent instant apps"
	@echo "make agent-app-run    Start a web instant app (pass APP=<app-id> [PORT=...])"
	@echo "make agent-app-runtime Show persisted runtime state for an instant app (pass APP=<app-id>)"
	@echo "make agent-app-stop   Stop a running instant app (pass APP=<app-id>)"
	@echo "make mcp-up           Start the MCP stack with Docker Compose"
	@echo "make mcp-down         Stop the MCP stack"
	@echo "make mcp-logs         Tail MCP logs"

env-agent:
	@source ./scripts/load-agent-env.sh

env-mcp:
	@source ./scripts/load-mcp-env.sh

test-generator:
	@cd kobkob-kaidf-generator && bash scripts/check.sh

test-agent:
	@cd agent-aidf && bash scripts/check.sh

test-mcp:
	@cd mcp-aidf && bash scripts/check.sh

test-all: test-generator test-agent test-mcp

install-generator:
	@cd kobkob-kaidf-generator && bash scripts/bootstrap.sh

install-agent:
	@cd agent-aidf && bash scripts/bootstrap.sh

install-mcp:
	@cd mcp-aidf && bash scripts/bootstrap.sh

ensure-generated-repo:
	@source ./scripts/load-agent-env.sh >/dev/null && \
	if [[ ! -d "$$AIDF_REPO_ROOT" ]]; then \
		echo "Default generated repository not found at $$AIDF_REPO_ROOT"; \
		echo "Generating it now..."; \
		$(MAKE) generate-default; \
	fi

generate-default:
	@cd kobkob-kaidf-generator && bash scripts/dev.sh

generate-maturity:
	@cd kobkob-kaidf-generator && bash scripts/generate-maturity-pack-example.sh

generate-ethical:
	@cd kobkob-kaidf-generator && bash scripts/generate-ethical-pack-example.sh

agent-shell:
	@$(MAKE) ensure-generated-repo >/dev/null && source ./scripts/load-agent-env.sh && cd agent-aidf && bash scripts/bootstrap.sh && PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" shell

agent-status:
	@$(MAKE) ensure-generated-repo >/dev/null && source ./scripts/load-agent-env.sh && cd agent-aidf && bash scripts/bootstrap.sh && PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" status

agent-context:
	@$(MAKE) ensure-generated-repo >/dev/null && \
	source ./scripts/load-agent-env.sh && \
	cd agent-aidf && \
	bash scripts/bootstrap.sh && \
	if [[ -n "$$PROMPT" ]]; then \
		PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" context "$$PROMPT"; \
	else \
		PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" context; \
	fi

agent-mentor:
	@$(MAKE) ensure-generated-repo >/dev/null && \
	source ./scripts/load-agent-env.sh && \
	cd agent-aidf && \
	bash scripts/bootstrap.sh && \
	if [[ -n "$$ANSWER" ]]; then \
		PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" mentor "$$ANSWER"; \
	else \
		PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" mentor; \
	fi

agent-mentor-status:
	@$(MAKE) ensure-generated-repo >/dev/null && source ./scripts/load-agent-env.sh && cd agent-aidf && bash scripts/bootstrap.sh && PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" mentor --status

agent-mentor-reset:
	@$(MAKE) ensure-generated-repo >/dev/null && source ./scripts/load-agent-env.sh && cd agent-aidf && bash scripts/bootstrap.sh && PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" mentor --reset

agent-packs:
	@$(MAKE) ensure-generated-repo >/dev/null && source ./scripts/load-agent-env.sh && cd agent-aidf && bash scripts/bootstrap.sh && PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" packs

agent-apps:
	@$(MAKE) ensure-generated-repo >/dev/null && source ./scripts/load-agent-env.sh && cd agent-aidf && bash scripts/bootstrap.sh && PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" apps

agent-app-run:
	@if [[ -z "$(APP)" ]]; then echo "Usage: make agent-app-run APP=<app-id> [PORT=<port>]"; exit 1; fi
	@$(MAKE) ensure-generated-repo >/dev/null && source ./scripts/load-agent-env.sh && cd agent-aidf && bash scripts/bootstrap.sh && PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" app-run "$(APP)" $(if $(PORT),--port $(PORT),)

agent-app-runtime:
	@if [[ -z "$(APP)" ]]; then echo "Usage: make agent-app-runtime APP=<app-id>"; exit 1; fi
	@$(MAKE) ensure-generated-repo >/dev/null && source ./scripts/load-agent-env.sh && cd agent-aidf && bash scripts/bootstrap.sh && PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" app-runtime "$(APP)"

agent-app-stop:
	@if [[ -z "$(APP)" ]]; then echo "Usage: make agent-app-stop APP=<app-id>"; exit 1; fi
	@$(MAKE) ensure-generated-repo >/dev/null && source ./scripts/load-agent-env.sh && cd agent-aidf && bash scripts/bootstrap.sh && PYTHONPATH=src .venv/bin/python -m agent_aidf.legacy_cli --repo "$$AIDF_REPO_ROOT" app-stop "$(APP)"

mcp-up:
	@source ./scripts/load-mcp-env.sh && cd mcp-aidf && docker compose up --build -d

mcp-down:
	@source ./scripts/load-mcp-env.sh && cd mcp-aidf && docker compose down

mcp-logs:
	@source ./scripts/load-mcp-env.sh && cd mcp-aidf && docker compose logs -f

workspace-up:
	@echo "🤖 Iniciando infraestrutura local K-AIDF (Comunitária + OLMo)..."
	@docker-compose -f docker-compose.local.yml up -d
	@echo "⏳ Aguardando inicialização do modelo OLMo no Ollama..."
	@docker exec -it aidf-ollama ollama run olmo "Verify installation"
	@echo "🚀 Tudo pronto! Execute 'agent-aidf init' para começar com contexto local."

workspace-down:
	@docker-compose -f docker-compose.local.yml down
