# `kob models`

Lista os modelos que o provedor de inferência ativo serve, consultando o endpoint `GET <base>/v1/models`, e destaca o modelo que o `kob` usa agora.

```bash
kob models
kob models --json
```

## Saída

```text
ollama at http://localhost:11434
  ○ llama3:8b
  ● olmo2:7b-1124-instruct-q4_K_M (active)
```

O marcador `(active)` aponta o modelo resolvido da mesma forma que `build_controller()` faz. Se ele não estiver na lista, o `kob` avisa: o modelo precisa ser baixado no provedor, ou outro deve ser escolhido com `AIDF_MODEL` ou `--model`.

Com `--json`, a saída é um objeto estável para scripts:

```json
{
  "provider": "ollama",
  "base_url": "http://localhost:11434",
  "active_model": "olmo2:7b-1124-instruct-q4_K_M",
  "models": ["llama3:8b", "olmo2:7b-1124-instruct-q4_K_M"]
}
```

## Quando o provedor não responde

O comando espera poucos segundos. Se o servidor estiver fora do ar, recusar a conexão ou responder com erro, o `kob` imprime uma linha `error: ...` em stderr e sai com código `1`. Nenhum traceback é mostrado. Com `--json`, o erro vai para a saída como `{"error": "..."}`.

| Situação | Mensagem |
|---|---|
| Servidor inacessível | `The provider is not reachable at <url>` |
| Não responde a tempo | `The provider did not answer within 5s` |
| Chave recusada (401 ou 403) | `The provider refused the request ... Check its API key.` |
| `AIDF_CHAT_PROVIDER=none` | `No inference provider is configured` |

## Configuração

O `kob models` lê as mesmas variáveis que o chat:

| Provedor | Endpoint consultado | Variáveis |
|---|---|---|
| Ollama (padrão) | `$OLLAMA_HOST/v1/models` | `OLLAMA_HOST`, `AIDF_MODEL` |
| OpenAI ou compatível (`AIDF_CHAT_PROVIDER=openai`) | `$OPENAI_BASE_URL/models` | `OPENAI_BASE_URL`, `OPENAI_API_KEY` (enviada como `Bearer`), `OPENAI_MODEL` |

O comando não altera nenhuma configuração. Dentro do `kob shell`, a mesma listagem está disponível digitando `models`.

Veja também: [provedores de inferência](../05-models/inference-providers.md).
