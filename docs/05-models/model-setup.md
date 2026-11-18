# Model setup (`kob model-setup`)

O `model-setup` descreve, num arquivo só, como o modelo que o `kob` usa deve se comportar. O arquivo é `.kaidf/model-setup.json` e segue o contrato [`contracts/model-setup.schema.json`](../../contracts/model-setup.schema.json). Ele tem três camadas.

| Camada | O que define | Campos principais |
|---|---|---|
| Profile | quem é o modelo | `name`, `identity`, `mood`, `parameters`, `custom_instructions` |
| RAG (contexto e atenção) | o que ele pode citar do projeto | `rag.sources`, `rag.allowed_url_hosts`, `rag.top_k` |
| QLoRA (pesos) | um adaptador treinado sobre um modelo base | `qlora.base_model`, `qlora.adapter_path`, `qlora.dataset_manifest`, `qlora.fallback_to_base` |

## Comandos

```bash
kob model-setup init              # grava um perfil padrão (não sobrescreve sem --force)
kob model-setup check             # valida o perfil e mostra as camadas em uso
kob model-setup modelfile         # exporta um Modelfile do Ollama em .kaidf/Modelfile
```

`check` retorna `1` quando o perfil é inválido, quando o dataset do QLoRA tem problemas ou quando o plano está bloqueado.

## Moods

- `pragmatic-auditor`: direto e prático; aponta riscos concretos e o que mudar.
- `strict-auditor`: rigoroso; liga cada achado ao documento ou à regra de origem.
- `socratic-mentor`: guia por perguntas, deixando a conclusão para quem usa.

O mood muda a postura da resposta, não as regras de segurança do `kob`.

## RAG

- As fontes são caminhos dentro do projeto (arquivo ou pasta) e URLs cujo host esteja em `allowed_url_hosts`. Caminhos que saem do projeto, inclusive por symlink, são recusados.
- Os documentos são divididos pelos títulos Markdown. Um bloco de código nunca é cortado.
- A visibilidade segue a mesma regra do índice de documentos: `private` e níveis desconhecidos ficam de fora; sem o campo, vale `internal`.
- Um documento que contém uma credencial é retirado do contexto inteiro. A mensagem informa só o tipo da credencial, nunca o valor.
- A busca é lexical (BM25) e roda offline. Embeddings não estão implementados.

## QLoRA e o fallback

O plano escolhe a estratégia pelas camadas disponíveis:

| Estratégia | Quando |
|---|---|
| `base` | nenhuma camada ativa |
| `rag` | só o RAG está ativo |
| `qlora` | o adaptador existe e há GPU NVIDIA, sem RAG |
| `hybrid` | o adaptador está pronto e o RAG está ativo |
| `blocked` | o adaptador não está pronto e `fallback_to_base` é `false` |

Sem GPU (`nvidia-smi` ausente) ou sem o adaptador compilado, com `fallback_to_base: true` (o padrão), o `kob` segue com o modelo base e informa o motivo em `kob status` e em `kob model-setup check`.

O `modelfile` escreve `FROM <base>` e, quando o adaptador existe, `ADAPTER <caminho>`. Sem o adaptador, o arquivo traz um comentário de fallback e só o modelo base.

## Onde aparece

- `kob status` mostra o nome, o mood, a estratégia e o fallback. Com `--json`, o campo `model_setup` aparece apenas quando há perfil.
- O prompt do mentor recebe a voz do perfil e, com RAG ativo, os trechos recuperados para a pergunta. Um perfil inválido é registrado no log e ignorado; o mentor continua respondendo.
