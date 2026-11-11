# KAIDF-AMM: as cinco dimensões

O KAIDF-AMM (Kobkob AI Framework Assessment Maturity Matrix) é a matriz que o `kob audit` aplica a um repositório. Ela tem cinco dimensões, e cada uma reúne checks com uma severidade e um número de pontos. A soma dos pontos ganhos dá a pontuação de 0 a 100.

Ao auditar, o `kob` lê os arquivos e não executa nada. A auditoria verifica a *presença e a legibilidade* dos artefatos, não a qualidade do seu conteúdo. Por isso uma pontuação alta não substitui a revisão humana.

## 1. Soberania de dados e perímetro (`data-sovereignty`)

| Check | Pontos | Verifica |
|---|---|---|
| `no-credentials` | 10 | nenhuma chave de API, segredo ou `.env` nos arquivos versionados |
| `pii-masking-rules` | 10 | regras de mascaramento de PII definidas em `policy/pii-masking-rules.yaml` |

## 2. Metodologia como código (`methodology-as-code`)

| Check | Pontos | Verifica |
|---|---|---|
| `kaidf-scaffold` | 4 | o scaffold `.kaidf/` (ou a raiz, num repositório gerado) está presente |
| `mentor-state` | 4 | `mentor-workflow.json` é válido |
| `specs-parse` | 4 | os YAML de `specs/` fazem parse |
| `front-matter-v2` | 4 | os documentos Markdown trazem o Front Matter v2 |
| `skills-manifest` | 4 | `skills.yaml` registra skills válidas |

## 3. Conformidade regulatória (`regulatory-compliance`)

| Check | Pontos | Verifica |
|---|---|---|
| `risk-assessment` | 5 | artefato de avaliação de risco presente |
| `hitl-config` | 5 | configuração de human-in-the-loop presente |
| `dataset-audit` | 5 | manifesto de auditoria do dataset presente |

## 4. Guardrails determinísticos (`deterministic-guardrails`)

| Check | Pontos | Verifica |
|---|---|---|
| `ci-workflows` | 10 | workflows de CI presentes em `.github/workflows/` |
| `blocking-gates` | 10 | os gates de CI não podem falhar em silêncio |

## 5. Custo e saúde da infraestrutura (`cost-infrastructure-health`)

| Check | Pontos | Verifica |
|---|---|---|
| `budget-caps` | 10 | teto de tokens e timeout de requisição configurados em `policy/budget.yaml` |

## Como ler o resultado

```bash
kob audit                      # relatório legível
kob audit --severity critical  # só os achados críticos
kob audit --json               # resultado completo, com todos os checks
```

No `--json`, cada check traz `id`, `title`, `severity`, `points`, o caminho verificado e a remediação. Use `--fail-under` e `--fail-on-critical` para transformar a auditoria em gate de CI. Veja [`kob audit`](../03-commands/audit.md).

## Cobertura planejada

A versão 1.0 pontua apenas a presença e a legibilidade. Verificações de conteúdo, como mapeamentos regulatórios, hooks de pre-commit, gates de segurança e timeouts de requisição, estão previstas para a v1.1.
