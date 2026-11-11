# `kob help`

Mostra a lista de comandos, ou a ajuda completa de um comando.

## Uso

```bash
kob help              # lista os comandos, com uma linha cada
kob help <comando>    # ajuda completa de um comando
kob help <comando> <subcomando>   # comandos aninhados
```

`kob help <comando>` imprime exatamente a mesma página que `kob <comando> -h`.

## Exemplos

```bash
kob help
kob help audit
kob help ext list
kob help appliance template
```

## Comando desconhecido

```text
$ kob help audt
kob help: unknown command 'audt' for 'kob'. Did you mean 'audit'? Available: init, status, ...
```

A saída de erro vai para `stderr`, com código `2`. Quando há um nome parecido, o `kob` sugere a correção.

## Reserva de nome

`help` é um nome reservado: extensões não podem registrar um comando com esse nome. Veja [runtime de extensões](../02-architecture/extensoes.md).
