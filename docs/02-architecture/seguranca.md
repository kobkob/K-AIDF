# Segurança e limites

Este documento lista as garantias que o `kob` e os componentes oferecem, e o que fica por conta do operador.

## Dados e provedores

- **Modelo local por padrão.** Sem configuração, o chat e o mentor usam o Ollama local. Dados não saem da máquina.
- **Nuvem só por escolha explícita.** Ter `OPENAI_API_KEY` no ambiente não desvia o tráfego para a nuvem. A troca exige `AIDF_CHAT_PROVIDER=openai`. Veja [provedores de inferência](../05-models/inference-providers.md).
- **Sem chaves versionadas.** O check `no-credentials` do `kob audit` procura chaves de API, segredos e arquivos `.env` nos arquivos versionados.

## Interface web

- A interface escuta em `127.0.0.1`. Requisições com um `Host` que não é loopback são recusadas, o que protege contra DNS rebinding.
- Requisições com `Origin` de outra origem são recusadas.
- As rotas de escrita, como `POST /api/mentor`, exigem um token de API no cabeçalho de autenticação. Tokens são comparados em tempo constante.

## Extensões

- Uma extensão roda código Python ao iniciar o `kob`. Instale apenas o que você confia.
- Instalações remotas pedem confirmação. `--sha256` fixa o digest do arquivo.
- Comandos embutidos não podem ser substituídos. Veja [runtime de extensões](extensoes.md).

## Modo YOLO

`kob --yolo` desativa as confirmações de segurança. Com ele, o `kob` pode gravar arquivos e executar comandos de shell sem perguntar, o que pode modificar ou apagar dados. Use só se entender e aceitar esse risco. O `kob` exibe um aviso ao ativá-lo.

## Gerador e shell

- `kob shell` e as ações de shell do agente passam por confirmação, a menos que o modo YOLO esteja ativo.
- O gerador roda a partir do seu próprio checkout, com o ambiente do gerador.

## MCP

O `mcp-aidf` exige `Authorization: Bearer <MCP_BEARER_TOKEN>` em toda requisição a `/mcp` e `/`. Documentos têm uma visibilidade (ACL) e um escopo de tenant: quem não está autenticado vê só os documentos públicos, e documentos ocultos se comportam como inexistentes.

## O que fica com o operador

- Revisar o conteúdo dos artefatos: a auditoria confere a presença, não a substância.
- Manter as chaves fora do repositório e rotacioná-las.
- Decidir quando aceitar um provedor em nuvem, de acordo com a política de dados da organização.
