# EasyPanel template for `mcp-aidf`

`easypanel.json` is an [EasyPanel](https://easypanel.io) schema that creates one App service running the K-AIDF MCP server. The step-by-step guide, in Portuguese, is [`docs/06-deploy/easypanel.md`](../../docs/06-deploy/easypanel.md).

## What it creates

- an App service `mcp-aidf`, built from this repository (`kobkob/K-AIDF`, branch `main`, build path `/`, Dockerfile `mcp-aidf/Dockerfile`)
- a domain on the service's generated host (`$(EASYPANEL_DOMAIN)`) that targets container port `8000`
- a volume `workspace` mounted at `/workspace`
- the environment `PORT=8000`, `MCP_PUBLIC_URL=https://$(PRIMARY_DOMAIN)`, `AIDF_REPO_ROOT=/workspace` and an empty `MCP_BEARER_TOKEN`

## Use

1. Generate a token: `openssl rand -hex 32`.
2. Copy `easypanel.json` and paste the token right after `MCP_BEARER_TOKEN=`. Do not commit the result.
3. In an EasyPanel project, open **Templates**, choose **Create From Schema**, paste the JSON and deploy the service.
4. Put a K-AIDF repository at the root of the `workspace` volume so that `search` and `fetch` have documents to index. The guide describes the layouts.

`MCP_BEARER_TOKEN` ships empty on purpose: a value published here would be a known token. With it empty, each server process generates its own token, so fill it in before the first deploy.

## Keeping it in sync

`mcp-aidf/tests/test_easypanel_template.py` checks this file against `mcp-aidf/Dockerfile` and `mcp-aidf/app.py`: the build path, the port, the variables and the volume. The build context is the repository root, because the image builds the `agent-aidf` engine from `agent-aidf/`. If the Dockerfile copies files from another place, the test fails until `source.path` and `build.file` here follow.

The image bundles the `agent-aidf` audit engine and `git`, so the maturity tools answer ([#71](https://github.com/kobkob/K-AIDF/issues/71)).
