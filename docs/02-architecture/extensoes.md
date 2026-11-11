# Runtime de extensões

As extensões acrescentam comandos, flags, handlers e interceptadores de prompt ao `kob`, sem alterar o pacote. Há duas origens: as **extensões embutidas** (que acompanham o `agent-aidf`, como a `ext` que implementa `kob -x`, e a `words`) e as **extensões do usuário**, instaladas em um diretório próprio.

## Onde ficam

- Extensões do usuário: `~/.kob/extensions/` por padrão. A variável `KOB_EXTENSIONS_DIR` troca o diretório.
- Cada extensão é uma pasta com um módulo Python que expõe `register(hooks)`.

## Como carregam

O `kob` carrega as extensões uma vez, na inicialização. Elas valem para a TUI, para o shell, para o mentor e para os comandos. Uma extensão instalada só passa a valer no próximo início do `kob`.

Ao registrar, uma extensão pode:

- **Adicionar flags de topo**, como `-x`, com `add_cli_arguments`.
- **Adicionar handlers de flag**, que rodam quando nenhum subcomando foi dado, com `add_cli_handler`.
- **Adicionar subcomandos**, com `add_subcommand(name, help, configure, handler)`.
- **Responder prompts antes do modelo**, com `add_prompt_interceptor`: a função devolve uma resposta, ou `None` para deixar o modelo responder.

## Regras de convivência

- Extensões **não podem substituir comandos embutidos**. Um subcomando com nome reservado, ou já reivindicado por uma extensão anterior, é recusado com um aviso no log.
- Os comandos embutidos, incluindo `help`, nunca chegam aos handlers de extensões.
- Uma extensão que falha ao carregar é marcada como `failed` e não derruba o `kob`.

## Instalação com `kob -x`

```bash
kob -x ./minha-extensao.tgz
kob -x https://exemplo.org/extensao.tgz --sha256 <hex>
kob -x https://exemplo.org/extensao.tgz --yes
```

Antes de gravar uma extensão, o `kob` mostra um resumo (nome, autor, versão, origem e SHA-256) e pede confirmação. Sem terminal para perguntar, a instalação remota falha, a menos que `--yes` seja dado. O instalador grava `.kob-install.json` com o SHA-256 do arquivo e de cada arquivo extraído.

## Integridade

`kob ext list` mostra o estado de cada extensão do usuário:

| Estado | Significado |
|---|---|
| `verified` | os arquivos batem com o registro da instalação |
| `MODIFIED` | algum arquivo mudou desde a instalação (o relatório lista quais) |
| `no-record` | a extensão não tem registro de instalação |
| `unreadable` | o registro não pôde ser lido |

Veja [`kob ext`](../03-commands/ext.md) para os flags.
