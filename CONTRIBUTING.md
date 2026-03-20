# Contributing

## Branch Policy

- default branch: `main`
- keep feature work in short-lived branches
- merge changes through reviewed pull requests when possible

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
AIDF_REPO_ROOT=/absolute/path/to/kobkob-kaidf python app.py
```

## Scope

- keep MCP protocol behavior and OAuth handling explicit
- avoid hard-coding content assumptions that should come from generated K-AIDF repositories
- document any connector-facing API or authentication changes in the README
