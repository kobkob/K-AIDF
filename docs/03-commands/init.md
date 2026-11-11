# `kob init`

Cria o diretório `.kaidf/` no projeto. É o primeiro passo para usar o K-AIDF em uma pasta.

## Uso

```bash
kob init [--force]
```

## Opções

| Flag | Efeito |
|---|---|
| `--force` | recria `.kaidf/` do zero, substituindo o existente |

Sem `--force`, um `.kaidf/` existente não é tocado: o comando mostra um erro e sugere `--force`.

## Exemplos

```bash
kob init                       # cria .kaidf/ no diretório atual
kob init --force               # recria .kaidf/ do zero
kob --project ~/work/acme init # inicializa outra pasta
```

## Saída

Em sucesso, imprime o nome do projeto e o caminho do `.kaidf/` criado, e sai com `0`. Se o projeto já estiver inicializado, sai com `1`.

## Veja também

- [`kob status`](status.md) para conferir o resultado.
- [`kob appliance init`](appliance.md) para configurar o `.kaidf/` a partir de um notebook.
