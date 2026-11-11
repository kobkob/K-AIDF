# Quickstart

Este guia leva você de um clone do repositório a um projeto K-AIDF auditado, em poucos minutos. Para os detalhes de instalação, veja [instalação](instalacao.md). Para o vocabulário, veja [conceitos](conceitos.md).

## 1. Prepare o ambiente

```bash
make install-agent      # cria o venv do agent-aidf e instala o comando `kob`
source agent-aidf/.venv/bin/activate
kob --version
```

## 2. Crie um projeto

Em uma pasta de projeto (ou use `--project <pasta>`):

```bash
cd ~/work/acme
kob init
```

`kob init` cria o diretório `.kaidf/`, que contém o scaffold do K-AIDF: o `README.md`, `docs/`, `policy/`, `specs/`, `data/manifests/` e o estado do mentor.

## 3. Veja o estado e a auditoria

```bash
kob status          # onde o kob enxerga o projeto e o runtime
kob audit           # pontua o repositório na matriz KAIDF-AMM
kob audit --severity high   # mostra só achados críticos e altos
```

`kob audit` não escreve nem executa nada. Ele só lê os arquivos e informa a pontuação, com um motivo e uma sugestão para cada check que perdeu pontos.

## 4. Converse com o mentor

```bash
kob mentor                  # mostra a pergunta pendente
kob mentor "resposta aqui"  # registra a resposta e avança
```

O mentor precisa de um modelo de linguagem. Por padrão, ele usa o Ollama local; veja [provedores de inferência](../05-models/inference-providers.md).

## 5. Abra a interface

```bash
kob ui          # interface web em http://127.0.0.1:8501
kob             # interface de terminal (TUI), sem subcomando
```

Veja [interfaces](../04-interfaces/README.md) para a diferença entre as duas.

## 6. Peça ajuda a qualquer momento

```bash
kob help            # lista os comandos
kob help audit      # ajuda completa de um comando
kob audit -h        # o mesmo, pela flag de ajuda
```

## Próximos passos

- [Arquitetura](../02-architecture/kaidf-amm.md): as cinco dimensões da matriz de auditoria.
- [Referência de comandos](../03-commands/README.md): todas as flags e exemplos.
- [Segurança](../02-architecture/seguranca.md): o que o `kob` faz e não faz por conta própria.
