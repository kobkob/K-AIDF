# `kob audit`

Pontua um repositório K-AIDF na matriz [KAIDF-AMM](../02-architecture/kaidf-amm.md). A auditoria é somente leitura: não escreve nem executa nada.

## Uso

```bash
kob audit [caminho] [--json] [--severity NÍVEL] [--fail-under N] [--fail-on-critical]
```

`caminho` é o repositório a auditar. O padrão é o diretório atual.

## Flags

### `--severity NÍVEL`

Mostra só os achados com severidade igual ou superior a `NÍVEL`. Valores, do mais grave ao menos grave: `critical`, `high`, `medium`, `low`. Filtra a exibição; a pontuação não muda. Com `--json`, o resultado lista sempre todos os checks.

### `--json`

Imprime o resultado completo em JSON, com todos os checks, pontos, caminhos verificados e remediações. Use para CI e dashboards.

### `--fail-under N`

Sai com código `1` quando a pontuação é menor que `N` (inteiro de 0 a 100). Serve como gate de CI.

### `--fail-on-critical`

Sai com código `1` quando existe qualquer achado crítico. Também serve como gate de CI.

Os dois gates podem ser combinados. Se ambos falharem, a saída é `1`.

## Códigos de saída

| Código | Significado |
|---|---|
| `0` | a auditoria rodou e nenhum gate falhou |
| `1` | um gate falhou (`--fail-under` ou `--fail-on-critical`) |
| `2` | o caminho não é um diretório válido, ou os argumentos estão errados |

## Exemplos

```bash
kob audit                         # pontua o diretório atual e imprime o relatório
kob audit ./acme-repo             # pontua outro repositório
kob audit --severity high         # só achados críticos e altos
kob audit --json > audit.json     # salva o resultado completo
kob audit --fail-under 80         # gate: falha se a pontuação for menor que 80
kob audit --fail-on-critical      # gate: falha com qualquer achado crítico
```

## Exemplo de CI

```yaml
- run: kob audit --fail-under 80 --fail-on-critical
```

## Escopo

A raiz auditada contém o `.kaidf/` quando ele existe, e o próprio diretório caso contrário. Credenciais são procuradas nos arquivos versionados da raiz. Os artefatos do scaffold são procurados primeiro no `.kaidf/`. Cada remediação informa o caminho que foi verificado.
