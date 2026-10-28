# Provedores de inferência da K-AIDF

Este documento descreve como o `kob` (o CLI do `agent-aidf`) escolhe o modelo que responde ao chat e ao mentor, como usar cada provedor e como implantar a stack on-premises com LocalAI em um ambiente corporativo.

## Arquitetura plug-and-play

O `kob` não conhece modelos específicos. Ele conhece dois protocolos e uma variável que escolhe qual deles usar:

| Caminho | Protocolo | Quando é usado |
|---|---|---|
| `OllamaChatController` | Ollama (`POST {OLLAMA_HOST}/api/generate`) | Padrão, inclusive quando `AIDF_CHAT_PROVIDER` não está definida |
| `OpenAIResponsesController` | OpenAI Responses (`POST {OPENAI_BASE_URL}/responses`) | Somente com `AIDF_CHAT_PROVIDER=openai` |

A seleção acontece em `build_controller()` (`agent-aidf/src/agent_aidf/controller.py`), que é a mesma para TUI, shell, mentor e interface web. Por isso, trocar o provedor é uma questão de ambiente, sem alterar código.

A regra de segurança é deliberada: **ter `OPENAI_API_KEY` no ambiente não basta para ir para a nuvem**. Uma chave residual nunca desvia o `kob` silenciosamente. A troca exige `AIDF_CHAT_PROVIDER=openai` explícito. `AIDF_CHAT_PROVIDER=none` desliga a IA e mantém apenas o modo stub.

## Escolhendo o provedor

| Provedor | Onde roda | Dados saem da organização? | Como ligar no `kob` | Quando usar |
|---|---|---|---|---|
| **Ollama** (padrão, `make workspace-up`) | Host ou container local | Não | Nada, ou `OLLAMA_HOST` e `AIDF_MODEL` | Desenvolvimento individual, máquinas modestas, modelos OLMo |
| **LocalAI** (`make workspace-localai`) | Container local, CPU ou GPU NVIDIA | Não | `AIDF_CHAT_PROVIDER=openai` + `OPENAI_BASE_URL` apontando para o LocalAI | Implantação corporativa on-premises, API compatível com OpenAI, múltiplos modelos num único endpoint |
| **OpenAI** (nuvem) | Infraestrutura da OpenAI | Sim | `AIDF_CHAT_PROVIDER=openai` + `OPENAI_API_KEY` | Quando a política de dados permite e é preciso o modelo de maior capacidade |
| **Groq** (nuvem) | Infraestrutura da Groq | Sim | `AIDF_CHAT_PROVIDER=openai` + `OPENAI_BASE_URL` da Groq + chave da Groq | Latência baixa em nuvem; ver a ressalva abaixo |

Ressalva sobre provedores de nuvem que não são a OpenAI: o caminho `openai` do `kob` fala o protocolo **Responses** (`/responses`), não apenas `/chat/completions`. Antes de usar um provedor terceiro com esse caminho, confirme que ele implementa `/responses` na versão contratada. O mesmo vale para o LocalAI, cuja cobertura de `/responses` depende da versão da imagem.

## Variáveis de ambiente

Defina no `.env` da raiz do workspace (copie de `.env.example`).

| Variável | Efeito | Valor típico |
|---|---|---|
| `AIDF_CHAT_PROVIDER` | Escolhe o provedor: `ollama` (padrão), `openai` ou `none` | `openai` para LocalAI ou nuvem |
| `OPENAI_BASE_URL` | Endpoint base do caminho `openai`. Só esta variável é lida pelo `kob`; não existe `OPENAI_API_BASE` | `http://localhost:8080/v1` (LocalAI) |
| `OPENAI_API_KEY` | Token enviado como `Bearer`. Em LocalAI sem chave configurada, qualquer valor não vazio serve | `local` (LocalAI) ou chave real (nuvem) |
| `OPENAI_MODEL` | Nome do modelo enviado no pedido. Deve ser exatamente um dos retornados por `GET /v1/models` | ex.: nome listado pelo LocalAI |
| `AIDF_CHAT_INSTRUCTIONS` | Instruções de sistema personalizadas (opcional) | vazio |
| `AIDF_CHAT_TIMEOUT_SECONDS` | Tempo máximo de espera por resposta. Aumente em CPU pura | `300` (padrão) ou mais |
| `OLLAMA_HOST` | Endpoint do Ollama (caminho padrão) | `http://localhost:11434` |
| `AIDF_MODEL` | Modelo do Ollama (caminho padrão) | preenchido por `make workspace-up` |

Para apontar o `kob` para um LocalAI na mesma máquina, o `.env` fica assim:

```bash
AIDF_CHAT_PROVIDER=openai
OPENAI_BASE_URL=http://localhost:8080/v1
OPENAI_API_KEY=local
OPENAI_MODEL=<nome-de-um-modelo-em-GET-/v1/models>
AIDF_CHAT_TIMEOUT_SECONDS=600
```

Para voltar ao Ollama, remova `AIDF_CHAT_PROVIDER` (ou deixe vazio). As demais variáveis podem ficar, pois são ignoradas.

## Implantação on-premises com LocalAI

### Pré-requisitos

- Docker Engine e Docker Compose v2 (`docker compose version` deve funcionar).
- Porta `8080` livre no host. Se o `mcp-aidf` estiver ativo pelo `docker-compose.local.yml`, ele também usa a `8080`; rode uma das stacks por vez ou altere a porta de um deles.
- Para GPU: driver NVIDIA e NVIDIA Container Toolkit configurados para Docker. Sem isso, a stack GPU não sobe.
- Disco para os modelos. Modelos de 7B quantizados ocupam alguns GB cada.

### Passo a passo

1. **Subir a stack.** Na raiz do repositório:

   ```bash
   make workspace-localai
   ```

   O alvo cria `./models` se faltar, sobe o serviço `localai` em segundo plano e só devolve o terminal quando o healthcheck (`GET /readyz`) responde. Se o tempo estourar, o comando falha e você pode consultar `docker compose -f docker-compose.localai.yml logs`.

2. **Verificar a API.**

   ```bash
   curl -s http://localhost:8080/v1/models
   ```

   A resposta lista os modelos disponíveis. Copie um dos `id` para `OPENAI_MODEL`.

3. **Adicionar modelos (opcional).** Coloque os arquivos do modelo e, se necessário, a configuração YAML do LocalAI em `./models`. A imagem AIO já traz modelos pré-configurados; os demais exigem arquivos adicionais. Reinicie com `make workspace-localai-down && make workspace-localai` depois de alterar a pasta.

4. **Configurar o `kob`.** Ajuste o `.env` conforme a seção de variáveis e rode:

   ```bash
   make agent-tui
   ```

   Faça uma pergunta simples. Se a resposta demorar, aumente `AIDF_CHAT_TIMEOUT_SECONDS`.

5. **Parar.** Quando não precisar mais:

   ```bash
   make workspace-localai-down
   ```

   Os modelos em `./models` permanecem no disco. Esse diretório fica fora do Git (`.gitignore`).

### Ativar GPU NVIDIA

O `docker-compose.localai.yml` vem configurado para CPU. Para usar CUDA:

1. Instale o driver NVIDIA e o NVIDIA Container Toolkit no host, e configure o runtime: `sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker`.
2. No arquivo, troque a imagem para `localai/localai:latest-aio-gpu-nvidia-cuda-12`.
3. Descomente o bloco `deploy` sob o serviço `localai`.
4. Rode `make workspace-localai` novamente.

### Ambientes sem acesso à internet

A primeira subida baixa a imagem do Docker Hub, e modelos baixados por galeria também precisam de rede. Em ambientes isolados, faça o pull da imagem `localai/localai:latest-aio-cpu` (ou a GPU) em uma máquina com acesso, exporte com `docker save`, importe no host com `docker load` e copie os arquivos de modelo para `./models` manualmente.

## Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| `make workspace-localai` falha por tempo esgotado | Primeira execução baixando imagem ou modelo, ou CPU lenta | Veja `docker compose -f docker-compose.localai.yml logs localai`; aumente `--wait-timeout` no Makefile se necessário |
| `kob` responde com erro de conexão em `localhost:8080` | Stack parada ou porta ocupada | `docker ps`; confirme que `mcp-aidf-server` não usa a 8080 |
| `kob` continua usando Ollama | `AIDF_CHAT_PROVIDER` não está como `openai` | Ajuste o `.env` e reinicie o `kob` |
| `kob` retorna 404 em `/responses` | A versão do LocalAI não implementa a Responses API | Atualize a imagem ou use Ollama até a compatibilidade estar confirmada |
| Erro de "nvidia" device driver ao subir | Toolkit NVIDIA ausente ou não configurado | Instale e configure o toolkit, ou volte para a imagem CPU |
