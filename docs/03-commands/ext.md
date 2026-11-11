# `kob ext` e `kob -x`

Duas peças cuidam das extensões. `kob ext list` inspeciona o que está carregado. `kob -x` instala uma extensão nova. Veja o [runtime de extensões](../02-architecture/extensoes.md) para o modelo completo.

## `kob ext list`

Lista cada extensão embutida e do usuário, com versão, autor, origem, estado de carregamento e integridade.

```bash
kob ext list          # texto
kob ext list --json   # JSON, schema_version 1
```

Estados de carregamento: `loaded`, `failed`, `disabled` ou `shadowed` (substituída por outra de mesmo nome). Para extensões do usuário, a integridade é `verified`, `MODIFIED` (com a lista dos arquivos alterados), `no-record` ou `unreadable`.

| Flag | Efeito |
|---|---|
| `--json` | imprime o inventário em JSON |

## `kob -x`: instalar uma extensão

`-x` é uma flag de topo, fornecida pela extensão embutida `ext`. Ela instala e não executa a extensão. A extensão passa a valer no próximo início do `kob`.

```bash
kob -x SOURCE [--sha256 HASH] [--yes]
```

| Argumento | Efeito |
|---|---|
| `SOURCE` | caminho local de um `.tgz`, ou URL `https://` de um `.tgz` |
| `--sha256 HASH` | recusa o arquivo se o SHA-256 não for igual a `HASH` |
| `--yes` | aprova sem perguntar. Obrigatório quando não há terminal para perguntar |

Antes de instalar, o `kob` mostra nome, autor, versão, origem e SHA-256, e pede confirmação. Extensões rodam código Python ao iniciar; instale apenas de autores em quem você confia.

## Exemplos

```bash
kob ext list
kob ext list --json
kob -x ./minha-extensao.tgz
kob -x https://exemplo.org/extensao.tgz --sha256 <hex-digest>
kob -x https://exemplo.org/extensao.tgz --yes
```

## Códigos de saída

| Código | Significado |
|---|---|
| `0` | listagem ou instalação concluída |
| `1` | a instalação falhou: arquivo inválido, digest diferente, ou confirmação negada |
| `2` | flags usadas fora de contexto, como `--yes` sem `-x` |
