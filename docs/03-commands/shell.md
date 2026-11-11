# `kob shell`

Abre um shell interativo no terminal, com o modelo de linguagem ativo. Use para perguntas rápidas sobre o projeto, sem a interface de terminal completa.

## Uso

```bash
kob shell [--model <nome>]
```

## Dentro do shell

- `help` lista os comandos disponíveis dentro do shell.
- `quit` encerra.

## Modelo

O modelo segue a mesma resolução dos demais comandos: `--model`, depois `AIDF_MODEL`, depois as variáveis do Ollama, e por fim o modelo padrão. Veja [modelos](../05-models/README.md).

## Exemplos

```bash
kob shell                          # abre o shell com o modelo configurado
kob --model olmo2:13b shell        # abre com um modelo específico
```

## Confirmações

Ações que escrevem arquivos ou executam comandos pedem confirmação, a menos que `--yolo` esteja ativo. Veja [segurança](../02-architecture/seguranca.md).
