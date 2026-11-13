# Implantar o `mcp-aidf` no EasyPanel

Este guia sobe o servidor MCP do K-AIDF em uma instância [EasyPanel](https://easypanel.io) a partir do template [`deploy/easypanel/easypanel.json`](../../deploy/easypanel/easypanel.json) e conecta clientes MCP a ele. O template é um JSON no formato de schema do EasyPanel: você cola o conteúdo no painel e ele cria o serviço.

## O que o template cria

| Item | Valor |
|---|---|
| Serviço | App `mcp-aidf`, construído a partir do GitHub (`kobkob/K-AIDF`, branch `main`, build path `/mcp-aidf`, `Dockerfile`) |
| Domínio | o domínio automático do serviço (`$(EASYPANEL_DOMAIN)`), com HTTPS, apontando para a porta `8000` do container |
| Volume | `workspace`, montado em `/workspace` |
| Ambiente | `PORT`, `MCP_PUBLIC_URL`, `AIDF_REPO_ROOT` e `MCP_BEARER_TOKEN` (vazio, você preenche) |

O repositório é público, então o EasyPanel constrói a imagem sem token do GitHub. Nenhuma imagem pronta é publicada: o primeiro deploy faz o build no seu servidor.

## Pré-requisitos

- Uma instância EasyPanel com um projeto criado. O guia foi escrito contra a documentação da versão 2.38.
- Domínios automáticos de serviço ativos no servidor, ou um domínio seu para apontar ao serviço.
- Acesso SSH ao servidor, para colocar os repositórios no volume.

## Passo a passo

1. **Gerar o token.** Ele é a única credencial do servidor.

   ```bash
   openssl rand -hex 32
   ```

2. **Preencher o token no JSON.** Copie o conteúdo de `deploy/easypanel/easypanel.json` e cole o token logo depois de `MCP_BEARER_TOKEN=`, antes das aspas que fecham o campo `env`. Não grave o arquivo com o token no Git.

3. **Importar.** No projeto, abra **Templates** e escolha **Create From Schema** (o botão fica no grupo **Custom**, como relatado nas versões 2.32 e 2.38; em versões mais antigas o grupo pode aparecer como **Developer**). Cole o JSON e confirme.

4. **Conferir e implantar.** No serviço `mcp-aidf`, confira em **Environment** as quatro variáveis e em **Domains** o domínio apontando para a porta `8000`. Clique em **Deploy**. No EasyPanel, salvar a maioria das configurações não as aplica: mudanças de ambiente e de volume só chegam ao container com um novo deploy. Para usar um domínio seu, adicione-o em **Domains** com a porta `8000`, marque-o como domínio principal e faça um novo deploy; `MCP_PUBLIC_URL` passa a usar esse domínio.

5. **Colocar os repositórios no volume.** Veja [O volume `/workspace`](#o-volume-workspace).

6. **Verificar.** Veja [Verificação](#verificação).

## Variáveis de ambiente

| Variável | Efeito | Valor no template |
|---|---|---|
| `PORT` | Porta em que o servidor escuta dentro do container. Deve ser igual à porta do domínio | `8000` |
| `MCP_PUBLIC_URL` | URL pública do servidor, sem `/mcp` no fim. É publicada no desafio `WWW-Authenticate` e em `/.well-known/oauth-protected-resource` | `https://$(PRIMARY_DOMAIN)` |
| `AIDF_REPO_ROOT` | Diretório que o servidor indexa e audita. Deve ser o ponto de montagem do volume | `/workspace` |
| `MCP_BEARER_TOKEN` | Token que todo cliente envia em `Authorization: Bearer <token>` | vazio |

O EasyPanel troca `$(PRIMARY_DOMAIN)` pelo domínio principal do serviço. Se você trocar o domínio principal, faça um novo deploy para o servidor ler o valor novo.

Não deixe `MCP_BEARER_TOKEN` vazio. Sem ele, cada processo do servidor gera um token próprio e o escreve no log: o token que você gerou no passo 1 é recusado em toda requisição (`401`), e um token copiado do log só funciona quando a requisição cai no mesmo processo.

O template não define `SECRET_KEY` nem `MCP_TOKEN_SCOPES`. A primeira só é exigida pelo `docker-compose.yml` local. A segunda é opcional e está descrita em [Tenant Scopes](../../mcp-aidf/README.md#tenant-scopes); um JSON inválido nela impede o servidor de iniciar.

## O volume `/workspace`

O servidor só lê `/workspace`. Nada no container clona ou grava ali, e a imagem não traz `git`. O layout decide o que funciona:

| Layout | O que funciona |
|---|---|
| 1. `/workspace` é a raiz de um repositório K-AIDF (`README.md`, `MANIFESTO.md`, `docs/`) | `search` e `fetch` indexam esses arquivos. Com o motor de auditoria na imagem, `evaluate_repository_maturity` sem argumentos audita esse repositório |
| 2. Vários repositórios em subdiretórios (`/workspace/<nome>/`) | Só auditoria, e só com o motor na imagem: `evaluate_repository_maturity` com `path: "<nome>"`. `search` e `fetch` não indexam subdiretórios e não retornam nada |

A imagem atual ainda não traz o motor de auditoria (veja [Limitações atuais](#limitações-atuais)). Até lá, só o layout 1 entrega ferramentas que funcionam.

Coloque os arquivos pelo host. O EasyPanel guarda um volume nomeado em `/etc/easypanel/projects/<projeto>/<serviço>/volumes/<volume>`:

```bash
# no servidor do EasyPanel, depois do primeiro deploy
DEST=/etc/easypanel/projects/<projeto>/mcp-aidf/volumes/workspace

# layout 1: o repositório é a raiz do volume, que precisa estar vazio
git clone --depth 1 https://github.com/<org>/<repo>.git "$DEST"
rm -rf "$DEST/.git"            # a imagem não traz git; veja Limitações atuais

chmod -R a+rX "$DEST"          # o container roda com um usuário sem privilégios
```

No layout 2, clone cada repositório em `"$DEST/<nome>"`, remova o `.git` de cada um e rode o mesmo `chmod`.

Se preferir um diretório seu, troque o volume por um **Bind mount** em **Storage**, com o seu caminho no host montado em `/workspace`, e faça um novo deploy. O usuário do container precisa conseguir ler esse diretório (`chmod -R a+rX <caminho>`). Bind mounts ficam fora dos backups de volume do EasyPanel.

O servidor relê o volume a cada requisição, então trocar os arquivos não exige deploy. Mantenha o volume enxuto: cada busca percorre a árvore inteira.

## Verificação

```bash
# sem token: responde 200 e mostra a URL pública que o servidor publica
curl -s https://<domínio>/.well-known/oauth-protected-resource

# com token: handshake MCP
curl -s -X POST https://<domínio>/mcp \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}'
```

Na primeira resposta, `resource` deve ser `https://<domínio>`. A segunda deve trazer `serverInfo` e `protocolVersion`. Abrir o domínio no navegador mostra `{"error":"authorization_required"}`, o que é esperado: a rota `/` também exige o token.

## Conectar clientes

O endpoint é `https://<domínio>/mcp`, no transporte Streamable HTTP (somente `POST`, sem stream SSE). A autenticação é o cabeçalho estático `Authorization: Bearer <token>`; o servidor não tem fluxo OAuth. Rode a verificação acima antes de configurar um cliente: com o token errado, alguns clientes mostram um erro de OAuth em vez do `401`.

As configurações abaixo seguem a documentação de cada cliente em novembro de 2026.

### Claude Code

```bash
claude mcp add --transport http kaidf https://<domínio>/mcp \
  --header "Authorization: Bearer <token>"
```

Em um `.mcp.json` de projeto, o campo `type` é obrigatório e o token pode vir de uma variável de ambiente:

```json
{
  "mcpServers": {
    "kaidf": {
      "type": "http",
      "url": "https://<domínio>/mcp",
      "headers": {
        "Authorization": "Bearer ${KAIDF_MCP_TOKEN}"
      }
    }
  }
}
```

### Claude Desktop

O Claude Desktop conecta a um servidor com token estático pela ponte [`mcp-remote`](https://github.com/punkpeye/mcp-remote), que exige Node.js 20 ou mais recente. Em **Settings → Developer → Edit Config** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "kaidf": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://<domínio>/mcp",
        "--header",
        "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "Bearer <token>"
      }
    }
  }
}
```

O cabeçalho vai sem espaços em `args` e o valor fica em `env`, porque alguns clientes quebram argumentos com espaço. Feche o aplicativo por completo e abra de novo. No log, as linhas do `mcp-remote` sobre descoberta de OAuth aparecem mesmo quando a conexão funciona.

Os conectores personalizados do Claude (**Customize → Connectors**; em planos Team e Enterprise, um Owner adiciona em **Organization settings → Connectors**) só servem aqui se a sua organização tiver a opção **Request headers**, que está em beta. Nesse caso a conexão parte da nuvem da Anthropic, e o domínio precisa ser público.

### Cursor

Em `~/.cursor/mcp.json` (global) ou `.cursor/mcp.json` (projeto):

```json
{
  "mcpServers": {
    "kaidf": {
      "url": "https://<domínio>/mcp",
      "headers": {
        "Authorization": "Bearer ${env:KAIDF_MCP_TOKEN}"
      }
    }
  }
}
```

Se o Cursor tentar um login OAuth em vez de usar o cabeçalho, configure o `mcp-remote` como no Claude Desktop.

### Roo Code

A extensão Roo Code foi descontinuada em maio de 2026. O formato abaixo é o da última documentação publicada, para o `mcp_settings.json` global ou o `.roo/mcp.json` do projeto:

```json
{
  "mcpServers": {
    "kaidf": {
      "type": "streamable-http",
      "url": "https://<domínio>/mcp",
      "headers": {
        "Authorization": "Bearer <token>"
      }
    }
  }
}
```

Esse arquivo fica com o token em texto puro. Prefira o `mcp_settings.json` global e não grave no Git um `.roo/mcp.json` com o token.

## Limitações atuais

- **Ferramentas de maturidade.** A imagem construída a partir de `mcp-aidf/` ainda não instala o motor de auditoria (`agent-aidf`). Até a issue [#71](https://github.com/kobkob/K-AIDF/issues/71), `get_maturity_scorecard` e `evaluate_repository_maturity` respondem que o motor não está instalado. `search` e `fetch` funcionam.
- **Repositórios com `.git`.** O motor de auditoria chama `git ls-files` quando o diretório auditado tem `.git`, e a imagem não traz `git`. Enquanto isso não mudar, copie os repositórios sem o diretório `.git`.
- **Volume com escrita.** O EasyPanel não tem opção de montagem somente leitura. O servidor não grava no volume, mas a garantia do `:ro` do `docker-compose.yml` local não existe aqui.
- **Versão.** O template segue a branch `main`, e cada deploy reconstrói a imagem com o que estiver nela. O deploy automático fica desligado (`autoDeploy: false`).

## Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| O domínio responde erro de gateway | A porta do domínio é diferente de `PORT` | Deixe as duas em `8000` e faça o deploy |
| `resource` mostra `http://localhost:7777` | `MCP_PUBLIC_URL` está vazia | Use `https://$(PRIMARY_DOMAIN)` e faça o deploy |
| `401` em toda requisição com o seu token, ou intermitente com um token copiado do log | `MCP_BEARER_TOKEN` está vazio no container (não foi preenchido, ou faltou o deploy depois de preencher) e cada processo gerou um token | Preencha o token e faça o deploy |
| `search` não retorna nada | `/workspace` está vazio, os documentos estão em subdiretórios, ou o usuário do container não consegue ler os diretórios do volume | Veja os layouts em [O volume `/workspace`](#o-volume-workspace) e rode de novo o `chmod -R a+rX` |
| `search` e `fetch` respondem `Internal error.` | O volume não está montado em `AIDF_REPO_ROOT`, ou um arquivo indexado (`README.md`, `MANIFESTO.md`, `.md` ou `.csv` em `docs/`) não é UTF-8, tem front matter YAML inválido ou não pode ser lido pelo usuário do container | Confira **Storage**, os arquivos do volume e as permissões |
| As ferramentas de maturidade dizem que o motor não está instalado | A imagem ainda não inclui o `agent-aidf` | Veja [Limitações atuais](#limitações-atuais) |
| `evaluate_repository_maturity` responde `Forbidden` | O token usado é um token com escopo de `MCP_TOKEN_SCOPES` | Use o token principal |
| O cliente abre um login OAuth ou mostra erro em `/register` | O token foi recusado ou não foi enviado | Repita a [Verificação](#verificação) com o mesmo token |
