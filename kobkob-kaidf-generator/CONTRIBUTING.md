# Contributing

## Branch Policy

- default branch: `main`
- keep feature work in short-lived branches
- merge changes through reviewed pull requests when possible

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run the basic checks before opening a change:

```bash
PYTHONPATH=src python -m pytest -q
```

## Scope

- keep schema and template changes explicit and reviewable
- preserve deterministic generation behavior
- avoid breaking the generated repository contract without documenting it
