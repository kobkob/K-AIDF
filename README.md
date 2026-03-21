# kobkob-kaidf-generator

A small Python CLI to generate a K-AIDF methodology repository scaffold from a declarative YAML spec.

## What it does
- Validates a YAML spec (JSON Schema)
- Creates folders/files deterministically
- Writes files from:
  - built-in template library (`templates/library/*`)
  - inline content in the spec
- Can emit version 2-style YAML front matter for markdown files through spec metadata fields

## Operational Scripts

The repository includes a small operational script set for the common local workflows:

- `scripts/dev.sh`
  Purpose: recreate a broken local virtual environment if needed, run the test suite, validate the default spec, and generate the default example into `out/`

- `scripts/check.sh`
  Purpose: run the fast local validation path without generating output

- `scripts/generate-v2-example.sh [out-dir]`
  Purpose: validate and generate the version 2 metadata example spec into the given output directory

- `scripts/generate-maturity-pack-example.sh [out-dir]`
  Purpose: validate and generate the first-class optional maturity-model doctrine pack example into the given output directory

These scripts are meant to be the stable local entrypoints described by this README.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Generate a repo from the example spec
PYTHONPATH=src python -m kaidf_gen.cli generate specs/kaidf.default.yaml --out ./out --force
```

## Recommended Local Flow

For the default development loop:

```bash
bash scripts/dev.sh
```

For a fast validation-only pass:

```bash
bash scripts/check.sh
```

For a version 2 metadata/front matter example:

```bash
bash scripts/generate-v2-example.sh
```

For the maturity-model doctrine pack example:

```bash
bash scripts/generate-maturity-pack-example.sh
```

## Commands

- `kaidf-gen validate <spec.yaml>`
- `kaidf-gen generate <spec.yaml> --out <dir> [--force]`

Direct module-based examples:

```bash
PYTHONPATH=src python -m kaidf_gen.cli validate specs/kaidf.default.yaml
PYTHONPATH=src python -m kaidf_gen.cli generate specs/kaidf.metadata-v2.example.yaml --out ./out-v2 --force
```

## Specs

The main specs currently in the repository are:

- `specs/kaidf.default.yaml`
  Purpose: baseline generated repository layout, including the canonical doctrine package under `docs/00-overview/`, a starter best-practice variant package used as initial example material, and version 2 front matter for doctrine documents

- `specs/kaidf.metadata-v2.example.yaml`
  Purpose: example generated repository using version 2-style metadata/front matter emission

- `specs/kaidf.maturity-model-pack.example.yaml`
  Purpose: first-class optional maturity-model doctrine pack using richer metadata on top of the default baseline

- `specs/kaidf.ethical-model-pack.example.yaml`
  Purpose: planned ethical-model doctrine pack translating manifesto ethics into principles, risks, controls, and governance artifacts

- `specs/contract.example.yaml`
  Purpose: machine-readable description of the repository contract

## Contracts

The downstream integration contract lives in:

- `docs/contract.md`

This is the current source of truth for:

- stable IDs
- document classes
- canonical doctrine package paths
- prompt exposure defaults
- version 2 front matter fields
- MCP indexing expectations
- agent editing expectations

## Spec design principles
- **Methodology-as-Code**: your K-AIDF variant is expressed as data.
- **Composable**: you can create multiple specs for different project types.
- **Deterministic**: same input spec => same output tree.

## License
MIT
