# TUI: interface de terminal

A TUI é aberta com `kob`, sem subcomando. Ela mostra um cabeçalho com o modelo ativo, o estado do projeto e um canvas com o histórico. Você digita um texto livre para falar com o agente, ou um comando com barra.

## Abrir

```bash
kob
kob --model olmo2:13b          # com um modelo específico
kob --yolo                     # sem confirmações (veja a segurança antes)
```

## Texto livre

Qualquer texto que não começa com `/` é enviado ao modelo ativo. A resposta aparece no canvas. Enquanto o modelo responde, uma linha de status mostra o tempo decorrido.

## Comandos com barra

| Comando | Efeito |
|---|---|
| `/copy` | copia a última resposta para a área de transferência |
| `/copy-all` | copia todo o canvas visível |
| `/init` | cria o `.kaidf/` com o padrão |
| `/status` | mostra o estado das cinco fases de entrega |
| `/mentor` | mostra a pergunta pendente do mentor, ou registra uma resposta |
| `/ui` | inicia a interface web do mentor |
| `/serve` | alias de `/ui` |
| `/exit` | encerra a interface web, se estiver rodando, e sai do `kob` |

Os mesmos fluxos existem como subcomandos: `/init` é `kob init`, `/mentor` é `kob mentor`, e assim por diante. Veja [a referência de comandos](../03-commands/README.md).

## Confirmações

Ações que escrevem arquivos ou executam comandos de shell pedem confirmação antes de rodar. O modo `--yolo` desliga essa etapa. Veja [segurança](../02-architecture/seguranca.md).
