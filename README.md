# kobkob-kaidf-generator

A small Python CLI to generate a K-AIDF methodology repository scaffold from a declarative YAML spec.

## What it does
- Validates a YAML spec (JSON Schema)
- Creates folders/files deterministically
- Writes files from:
  - built-in template library (`templates/library/*`)
  - inline content in the spec
- Optionally produces a client export pack (starter kit)

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Generate a repo from the example spec
kaidf-gen generate specs/kaidf.default.yaml --out ./out/kobkob-kaidf
```

## Commands

- `kaidf-gen validate <spec.yaml>`
- `kaidf-gen generate <spec.yaml> --out <dir> [--force]`

## Spec design principles
- **Methodology-as-Code**: your K-AIDF variant is expressed as data.
- **Composable**: you can create multiple specs for different project types.
- **Deterministic**: same input spec => same output tree.

## License
Add your preferred license in this repo.
