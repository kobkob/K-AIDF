# Interfaces

O K-AIDF tem duas interfaces para o mesmo projeto e o mesmo mentor. Escolha pela forma de trabalho.

| Interface | Como abrir | Melhor para |
|---|---|---|
| [TUI (terminal)](tui.md) | `kob` (sem subcomando) | conversar com o agente e rodar comandos sem sair do terminal |
| [WebUI (navegador)](webui.md) | `kob ui` | acompanhar as fases de entrega e conduzir o mentor visualmente |

Ambas leem o mesmo projeto e gravam o mesmo estado do mentor em `.kaidf/mentor-workflow.json`. Um passo registrado em uma aparece na outra.

Para tudo que não é conversa, como auditar ou gerar o scaffold, use a linha de comando. Veja a [referência de comandos](../03-commands/README.md).
