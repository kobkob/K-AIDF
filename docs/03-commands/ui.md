# `kob ui` e `kob serve`

Sobem a interface web do mentor: as fases de entrega do Maturity Model de um lado e o chat do mentor do outro. `kob serve` é um alias de `kob ui`, com as mesmas opções.

Veja a [interface web](../04-interfaces/webui.md) para o uso no navegador.

## Uso

```bash
kob ui [--port N] [--model <nome>]
kob serve [--port N] [--model <nome>]
```

## Opções

| Flag | Efeito |
|---|---|
| `--port N` | porta do servidor, um número de porta TCP válido. Padrão: `AIDF_UI_PORT`, ou `8501` |
| `--model <nome>` | modelo para esta execução |

O servidor escuta sempre em `127.0.0.1`. Para acessar de outra máquina, use um túnel SSH ou um proxy reverso sob a sua política de rede.

## Parar

Pressione `Ctrl+C` no terminal onde o comando roda.

## Exemplos

```bash
kob ui                              # http://127.0.0.1:8501
kob ui --port 9000                  # outra porta
AIDF_UI_PORT=9000 kob ui            # porta padrão pelo ambiente
kob serve --model llama3.1:8b       # mesmo comando, com modelo específico
```
