# Conceitos essenciais

## K-AIDF

K-AIDF é o framework de IA com governança da Kobkob. Ele define como um projeto de IA é conduzido do começo ao fim, com soberania de dados, metodologia como código, conformidade regulatória, guardrails determinísticos e controle de custo e infraestrutura. A matriz que mede isso é o [KAIDF-AMM](../02-architecture/kaidf-amm.md).

## Projeto e repositório

- **Projeto**: a pasta do trabalho do usuário. Pode ser escolhida com `--project`, ou é o diretório atual.
- **Repositório (repo root)**: a raiz que contém o conteúdo K-AIDF. Em um projeto criado com `kob init`, o conteúdo fica em `.kaidf/` dentro do projeto. Um repositório gerado pelo gerador pode ser auditado diretamente.
- **Override de repositório**: `--repo <pasta>` aponta o runtime para outra cópia do K-AIDF.

## Scaffold `.kaidf/`

Diretório criado por `kob init` (ou gerado por `kob gen`). Contém:

- `README.md` e `docs/`: a documentação do projeto. A doutrina canônica fica em `docs/00-overview/`.
- `policy/*.yaml`: regras de PII, human-in-the-loop, orçamento.
- `specs/*.yaml`: especificações lidas pelo gerador e pelo auditor.
- `data/manifests/*.yaml`: manifesto de auditoria dos dados.
- `mentor-workflow.json`: o estado do fluxo do mentor.

Os artefatos marcados com `placeholder: true` pontuam zero na auditoria até serem preenchidos.

## Fases de entrega

O `kob status` e a interface web mostram as cinco fases de entrega do K-AIDF. Cada fase tem entregáveis (pacotes de documentos) que o mentor orienta a preencher.

## Mentor

O mentor é o fluxo guiado que conduz o projeto pelas perguntas da metodologia. O estado é persistido em `.kaidf/mentor-workflow.json`, então você pode parar e continuar depois. Use `kob mentor` no terminal ou a [interface web](../04-interfaces/webui.md).

## Auditoria

`kob audit` pontua o repositório de 0 a 100 nas cinco dimensões da KAIDF-AMM. Cada check tem uma severidade (`critical`, `high`, `medium`, `low`) e um custo em pontos. Veja [a referência de `kob audit`](../03-commands/audit.md).

## Extensões

Funcionalidades do `kob` podem ser adicionadas por extensões, instaladas com `kob -x`. Veja [extensões](../02-architecture/extensoes.md).

## Provedor de inferência e modelo

O `kob` fala com um modelo de linguagem por um provedor: o Ollama local (padrão), um servidor compatível com a API da OpenAI (LocalAI ou nuvem). O modelo é escolhido por `--model`, por `AIDF_MODEL` ou pelas variáveis do provedor. Veja [modelos](../05-models/README.md).
