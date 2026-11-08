# kobkob-kaidf-generator

A small Python CLI to generate a K-AIDF methodology repository scaffold from a declarative YAML spec.

## What it does

- Validates a YAML spec (JSON Schema)
- Creates folders/files deterministically
- Writes files from:
  - built-in template library (`templates/library/*`)
  - inline content in the spec
  - the spec's `audit_matrix` block (the KAIDF-AMM CSV and dimension check tables, see below)
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

- `scripts/generate-ethical-pack-example.sh [out-dir]`
  Purpose: validate and generate the first-class optional ethical-model doctrine pack example into the given output directory

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

For the ethical-model doctrine pack example:

```bash
bash scripts/generate-ethical-pack-example.sh
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
  Purpose: first-class optional ethical-model doctrine pack translating manifesto ethics into principles, risks, controls, and governance artifacts

- `specs/contract.example.yaml`
  Purpose: machine-readable description of the repository contract

## Audit matrix content

`specs/kaidf.default.yaml` carries an `audit_matrix` block: the KAIDF-AMM v1.0 matrix, five dimensions of 20 points and 15 checks. The block mirrors the `kob audit` engine (`agent-aidf`'s `audit.py`, `DIMENSION_SPECS`), which is what scores a repository; in v1.0 the engine checks the presence and parseability of the listed artifacts, not their substance. `agent-aidf/tests/test_audit_matrix_contract.py` fails when the block and the engine differ in any id, name, title or point, and the `agent-aidf` CI workflow runs it whenever that spec changes.

The matrix documents under `docs/30-kaidf-amm/` are rendered from the block, so they cannot drift from it:

- `content: "audit_matrix:csv"` renders `audit-matrix.csv` (columns `dimension_id,dimension,check_id,check,points,evidence,status,auditor_notes`, one row per check, `status` and `auditor_notes` empty)
- a line `<!-- audit_matrix:summary <dimension-id> -->` in a library template, or in inline content, is replaced by that dimension's `summary` as written (Markdown allowed), and a line `<!-- audit_matrix:checks <dimension-id> -->` by its check table (`Check | Criterion | Points | Evidence required`, cells escaped). The dimension pages in `templates/library/docs/30-kaidf-amm/dimensions/` carry both markers, so their narrative has a single source too

All of them fail with `GenerationError` when the spec has no `audit_matrix` block, a marker names an unknown dimension or kind, or a dimension has no `summary`. `validate_spec` still checks that each dimension's checks add up to its `max_points` and that the dimensions add up to `total_points`.

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
