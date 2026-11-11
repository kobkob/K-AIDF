# Modelos e provedores de inferência

O `kob` não tem um modelo fixo. Ele fala com um provedor, e o provedor serve um modelo. A escolha segue uma ordem de precedência, e a mesma regra vale para a TUI, o shell, o mentor e a interface web.

## Provedores

| Provedor | Protocolo | Onde roda | Quando usar |
|---|---|---|---|
| **Ollama** (padrão) | Ollama (`/api/generate`) | local, em Docker ou no host | desenvolvimento individual e máquinas modestas, com modelos OLMo |
| **LocalAI** | API compatível com OpenAI (`/v1/responses`) | local, CPU ou GPU NVIDIA | implantação corporativa on-premises, com vários modelos atrás de um endpoint |
| **OpenAI-compatible** (nuvem) | API da OpenAI (`/v1/responses`) | fora da organização | quando a política de dados permite e é preciso um modelo maior |

O caminho compatível com OpenAI usa `AIDF_CHAT_PROVIDER=openai`, `OPENAI_BASE_URL` e `OPENAI_MODEL`. Ele fala o protocolo **Responses**, então confirme que o servidor implementa `/responses` antes de usá-lo.

## Ordem de precedência do modelo

Para o modelo local (Ollama), o `kob` resolve nesta ordem, e a primeira definida vence:

1. `--model <nome>` na linha de comando. Ele grava o valor em `AIDF_MODEL` para o processo, então vale só para aquela execução.
2. `AIDF_MODEL`, preenchido por `make workspace-up` com a variante escolhida para a máquina.
3. `AIDF_OLLAMA_MODEL`.
4. `OLLAMA_MODEL`.
5. O padrão `olmo2:7b-1124-instruct-q4_K_M`. Enquanto nenhuma variável estiver definida, a TUI mostra o rótulo `OLMo 3.1 local`.

Para o caminho compatível com OpenAI (`AIDF_CHAT_PROVIDER=openai`), `--model` grava em `OPENAI_MODEL`, que é a variável usada nesse caminho.

## Escolher o provedor

O provedor padrão é o Ollama. Ter `OPENAI_API_KEY` no ambiente **não** muda o provedor: a troca exige `AIDF_CHAT_PROVIDER=openai` explícito. `AIDF_CHAT_PROVIDER=none` desliga a IA e mantém só o modo stub.

## Documentação detalhada

- [Provedores de inferência](inference-providers.md): variáveis de ambiente, exemplo de `.env`, implantação on-premises com LocalAI, GPU NVIDIA e ambientes sem internet.

## Verificação

```bash
kob status
kob --model <nome> shell     # confirma o modelo usado em uma execução
```

O nome do modelo ativo aparece no cabeçalho da TUI.
