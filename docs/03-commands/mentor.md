# `kob mentor`

Continua o fluxo guiado do mentor. O mentor faz perguntas da metodologia K-AIDF, registra as respostas e avança. O estado é salvo no projeto, então o fluxo pode ser retomado em outra sessão.

É preciso ter um projeto inicializado com [`kob init`](init.md).

## Uso

```bash
kob mentor [resposta] [--status] [--reset]
```

## Flags

| Forma | Efeito |
|---|---|
| `kob mentor` | mostra a pergunta pendente |
| `kob mentor "resposta"` | registra a resposta e mostra a próxima pergunta |
| `kob mentor --status` | mostra o progresso do fluxo |
| `kob mentor --reset` | apaga o estado do fluxo e recomeça |

`--model` também é aceito (`kob --model <nome> mentor`).

## Exemplos

```bash
kob mentor
kob mentor "Duas equipes compartilham o mesmo repositório"
kob mentor --status
kob mentor --reset
kob --model llama3.1:8b mentor
```

## Estado

O progresso fica em `.kaidf/mentor-workflow.json`. A auditoria verifica que esse arquivo é válido (check `mentor-state`).

Se o projeto não estiver inicializado, o comando mostra a mensagem de erro e sai com `1`.

## Veja também

- [Interface web](../04-interfaces/webui.md): o mesmo fluxo, com um chat e as fases de entrega.
