# Instalação

## Requisitos

- Python 3.10 ou superior.
- `make` e `git`.
- Opcional, para o modelo local: Docker e Docker Compose (o Ollama roda em container).

## Componentes

O repositório reúne três componentes, cada um com seu venv:

| Componente | Pasta | O que entrega |
|---|---|---|
| `agent-aidf` | `agent-aidf/` | o comando `kob` (CLI, TUI, interface web, mentor) |
| `kobkob-kaidf-generator` | `kobkob-kaidf-generator/` | o gerador de scaffold (`kob gen` chama o gerador) |
| `mcp-aidf` | `mcp-aidf/` | o servidor MCP de busca e leitura de documentos |

## Instalação

```bash
make install-generator   # venv do gerador
make install-agent       # venv do agent-aidf, instala o `kob`
make install-mcp         # venv do mcp-aidf
make test-all            # roda as três suítes de testes
```

Ative o venv do agente para usar o `kob` diretamente:

```bash
source agent-aidf/.venv/bin/activate
kob --version
```

## Modelo local (opcional, recomendado)

```bash
make workspace-up        # detecta RAM, disco e GPU, sobe o Ollama e baixa o modelo OLMo adequado
make agent-tui           # abre o kob com o modelo local
make workspace-down      # para a stack
```

O `make workspace-up` escolhe a variante do modelo pela máquina. Para forçar uma variante, defina `AIDF_OLLAMA_MODEL` antes. Veja [provedores de inferência](../05-models/inference-providers.md) para a lista completa de variáveis.

## Verificação

```bash
kob status
kob help
```

Se `kob` não for encontrado, confirme que o venv do `agent-aidf` está ativo, ou execute `agent-aidf/.venv/bin/kob` diretamente.
