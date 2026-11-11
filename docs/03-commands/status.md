# `kob status`

Mostra onde o `kob` enxerga o projeto e o runtime do K-AIDF. Só lê; não altera nada.

## Uso

```bash
kob status
```

## Saída

```text
project_root: /home/ana/work/acme
repo_root: /home/ana/work/acme/.kaidf
has_kaidf: yes
pack_count: 2
mentor_step_count: 5
```

| Campo | Significado |
|---|---|
| `project_root` | a pasta do projeto |
| `repo_root` | a raiz do runtime K-AIDF que o `kob` está usando |
| `has_kaidf` | se `.kaidf/` existe |
| `pack_count` | quantos pacotes de documentos estão instalados |
| `mentor_step_count` | quantos passos do mentor estão registrados |

## Exemplos

```bash
kob status                              # estado do diretório atual
kob --project ~/work/acme status        # estado de outro projeto
kob --repo ~/src/K-AIDF status          # usa um checkout específico como runtime
```
