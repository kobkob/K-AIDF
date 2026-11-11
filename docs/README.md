# Documentação do K-AIDF

Esta pasta é organizada em seções numeradas. Comece pela primeira e avance conforme a necessidade.

| Seção | Conteúdo |
|---|---|
| [01-basics](01-basics/quickstart.md) | quickstart, instalação e conceitos essenciais |
| [02-architecture](02-architecture/kaidf-amm.md) | as cinco dimensões da KAIDF-AMM, o runtime de extensões e a segurança |
| [03-commands](03-commands/README.md) | referência da CLI `kob` e de cada subcomando |
| [04-interfaces](04-interfaces/README.md) | a interface web (WebUI) e a interface de terminal (TUI) |
| [05-models](05-models/README.md) | provedores de inferência: Ollama, LocalAI, compatíveis com OpenAI e `AIDF_MODEL` |

Os documentos do repositório na raiz, como o [README](../README.md), o [MANIFESTO](../MANIFESTO.md) e o [CHANGELOG](../CHANGELOG.md), continuam no lugar.

## Onde estão os outros componentes

- `agent-aidf/`: o comando `kob`. Seu próprio README descreve a instalação do pacote.
- `kobkob-kaidf-generator/`: o gerador de scaffold. O contrato de integração fica em `kobkob-kaidf-generator/docs/contract.md`.
- `mcp-aidf/`: o servidor MCP. Seu README descreve as ferramentas `search`, `fetch` e as de maturidade.
