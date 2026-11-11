# WebUI: interface web do mentor

A interface web é iniciada com `kob ui` (ou `kob serve`). Ela mostra as fases do Maturity Model e o chat do mentor, no mesmo estado que a TUI e o comando `kob mentor` usam.

## Abrir

```bash
kob ui                    # http://127.0.0.1:8501
kob ui --port 9000        # outra porta
```

Abra o endereço no navegador. O servidor escuta somente no próprio computador.

## O que você vê

- **Fases de entrega**: as cinco fases do K-AIDF, com o progresso de cada uma. O mesmo estado aparece em `kob status`.
- **Chat do mentor**: a pergunta pendente e o campo de resposta. Cada resposta avança o fluxo, como em `kob mentor "resposta"`.

## Encerrar

Pressione `Ctrl+C` no terminal que roda `kob ui`, ou use `/exit` na TUI.

## Segurança

- O servidor só aceita requisições cujo `Host` é de loopback. Isso impede que uma página externa acesse a interface por DNS rebinding.
- Requisições com `Origin` de outra origem são recusadas.
- As rotas que alteram estado, como o envio de respostas ao mentor, exigem o cabeçalho `X-KAIDF-Token`. O token é gerado a cada início do servidor, nunca é gravado em disco, e a página servida pela própria interface já o inclui.

Para acesso remoto, prefira um túnel SSH a expor a porta na rede. Veja [segurança](../02-architecture/seguranca.md).

## Porta

A porta vem de `--port`, depois da variável `AIDF_UI_PORT`, depois do padrão `8501`.
