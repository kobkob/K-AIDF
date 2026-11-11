# `kob appliance`

Configura um projeto K-AIDF a partir de um notebook Jupyter. Serve para ambientes como Google Colab, Kaggle e JupyterLab, onde o operador quer criar o workspace com poucos cliques.

O notebook é tratado como dado: o `kob` lê a célula marcada com a tag `kaidf-config` e **não executa nenhuma célula**. Notebooks com chaves de aparência secreta são recusados.

## `kob appliance template`

Escreve um notebook inicial com células de instalação, `init` e auditoria, e a célula `kaidf-config` para editar.

```bash
kob appliance template FILE.ipynb [--force]
```

| Flag | Efeito |
|---|---|
| `--force` | sobrescreve `FILE.ipynb` se ele já existir |

## `kob appliance init`

Cria `.kaidf/` se ele não existir e grava as configurações do notebook em `.kaidf/appliance.yaml`, junto com o nome, o título e o SHA-256 do notebook.

```bash
kob appliance init --from-notebook FILE.ipynb [--force]
```

| Flag | Efeito |
|---|---|
| `--from-notebook FILE.ipynb` | notebook com a célula `kaidf-config`. Obrigatório |
| `--force` | recria `.kaidf/` do zero em vez de manter o existente |

### Campos de `kaidf-config`

A célula contém um bloco YAML delimitado por cercas:

````markdown
```yaml
project_name: acme
model: olmo2:7b-1124-instruct-q4_K_M
audit_fail_under: 80
```
````

| Campo | Efeito |
|---|---|
| `project_name` | nome do projeto |
| `model` | modelo a registrar para o projeto |
| `audit_fail_under` | pontuação mínima usada pelo gate de auditoria |

## Exemplos

```bash
kob appliance template kaidf-start.ipynb
kob appliance init --from-notebook kaidf-start.ipynb
kob appliance init --from-notebook kaidf-start.ipynb --force
```

## Saída e códigos

Em sucesso, mostra o caminho configurado, se o workspace foi criado ou mantido, as configurações e o caminho do registro, e sai com `0`. Erros de notebook ou de configuração saem com `1`.
