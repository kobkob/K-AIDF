# Referência da CLI `kob`

O `kob` é o ponto de entrada do `agent-aidf`. Sem argumentos, abre a [interface de terminal](../04-interfaces/tui.md). Com um subcomando, executa a ação e sai.

```bash
kob [opções globais] <comando> [argumentos]
```

## Opções globais

| Opção | Efeito |
|---|---|
| `--project <pasta>` | usa outra pasta como projeto (padrão: diretório atual) |
| `--repo <pasta>` | aponta o runtime para outra cópia do K-AIDF |
| `--model <nome>` | modelo para esta execução. Vale sobre `AIDF_MODEL`, `AIDF_OLLAMA_MODEL` e `OLLAMA_MODEL`. Veja [modelos](../05-models/README.md) |
| `--yolo` | desativa as confirmações de segurança. Veja [segurança](../02-architecture/seguranca.md) |
| `-v`, `--version` | mostra a versão |
| `-h`, `--help` | mostra a ajuda |

## Comandos

| Comando | Para que serve | Página |
|---|---|---|
| `kob init` | cria o `.kaidf/` do projeto | [init](init.md) |
| `kob status` | mostra o estado do projeto e do runtime | [status](status.md) |
| `kob audit` | pontua o repositório na KAIDF-AMM | [audit](audit.md) |
| `kob mentor` | continua o fluxo do mentor | [mentor](mentor.md) |
| `kob shell` | shell interativo com o modelo | [shell](shell.md) |
| `kob ui` (`kob serve`) | interface web do mentor | [ui](ui.md) |
| `kob compile` (`kob gen`) | gera o scaffold a partir de uma spec | [compile](compile.md) |
| `kob ext` e `kob -x` | lista e instala extensões | [ext](ext.md) |
| `kob appliance` | configura o projeto a partir de um notebook | [appliance](appliance.md) |
| `kob help` | lista os comandos ou explica um deles | [help](help.md) |

## Ajuda

Cada comando aceita `-h`, que mostra a descrição, as flags e exemplos. `kob help <comando>` mostra a mesma página, e aceita comandos aninhados, como `kob help ext list`.

## Códigos de saída

| Código | Significado |
|---|---|
| `0` | o comando rodou e nenhum gate falhou |
| `1` | erro de execução, ou um gate de `kob audit` falhou |
| `2` | uso incorreto: argumento inválido, comando desconhecido ou caminho inválido |

## Variáveis de ambiente

| Variável | Efeito |
|---|---|
| `AIDF_UI_PORT` | porta padrão de `kob ui` e `kob serve` (padrão: `8501`) |
| `KOB_EXTENSIONS_DIR` | diretório das extensões do usuário |
| `AIDF_CHAT_PROVIDER`, `AIDF_MODEL`, `OPENAI_BASE_URL` | provedor e modelo. Veja [provedores de inferência](../05-models/inference-providers.md) |
