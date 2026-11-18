# `kob compile` e `kob gen`

Rodam o gerador do K-AIDF sobre uma especificação e escrevem o scaffold em `--out`. `kob gen` é um alias de `kob compile`, com as mesmas opções.

O gerador vem do componente `kobkob-kaidf-generator`, importado como o pacote `kaidf_gen` e executado dentro do próprio `kob`. O `kob` não instala nada em tempo de execução e não procura o gerador ao lado do projeto. Ele usa, nesta ordem:

1. o pacote `kaidf_gen` instalado no Python do `kob` (`pip install` do `kobkob-kaidf-generator`);
2. o checkout indicado por `KAIDF_GENERATOR_DIR`, cujo `src/` entra no caminho de importação. É o override para desenvolvimento.

Sem nenhum dos dois, o comando termina com `error: The K-AIDF generator is not installed...` e código 1. O spec padrão vem dentro do pacote (`kaidf_gen/specs/kaidf.default.yaml`), então quem instala o gerador não precisa do checkout.

## Uso

```bash
kob compile [spec] [--out PASTA] [--force]
kob gen [spec] [--out PASTA] [--force]
```

## Opções

| Argumento ou flag | Efeito |
|---|---|
| `spec` | arquivo YAML de especificação. Sem ele, usa `specs/kaidf.default.yaml` do gerador |
| `--out PASTA` | destino do scaffold. Padrão: `./out` |
| `--force` | sobrescreve arquivos que já existem em `--out` |

Caminhos relativos são resolvidos a partir do diretório onde você roda o `kob`, não a partir do gerador.

## Exemplos

```bash
kob gen                                    # gera o padrão em ./out
kob compile my-spec.yaml --out ./acme      # gera a partir da sua spec
kob gen my-spec.yaml --out ./acme --force  # gera e sobrescreve
```

## Verificação

Depois de gerar, audite o resultado:

```bash
kob audit ./acme
```

## Veja também

- [Especificações e contrato do gerador](../01-basics/conceitos.md#scaffold-kaidf)
- [`kob audit`](audit.md)
