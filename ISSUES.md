# K-AIDF Open Issues

This file summarizes the currently open issues visible on the GitHub repository as of 2026-09-22.

- [#34](https://github.com/kobkob/K-AIDF/issues/34) - Libraries to integrate the framework into other systems
- [#33](https://github.com/kobkob/K-AIDF/issues/33) - [testing] Zero coverage: TUI, web UI, REPL, i18n, OAuth endpoints, visibility
- [#32](https://github.com/kobkob/K-AIDF/issues/32) - [bug][i18n] Front matter parser rejects CRLF; `allow_unicode=False` mangles PT titles
- [#31](https://github.com/kobkob/K-AIDF/issues/31) - [bug] Loose `is_affirmative("done")`; unvalidated `--port` crashes the REPL
- [#30](https://github.com/kobkob/K-AIDF/issues/30) - [security] Web UI `POST /api/mentor` runs the full workflow without auth/CSRF
- [#29](https://github.com/kobkob/K-AIDF/issues/29) - [security] Dockerfile hardening: root user, dev server, unpinned deps, placeholder SECRET_KEY
- [#28](https://github.com/kobkob/K-AIDF/issues/28) - [cleanup] Hardcoded production URL in 401 body; dead `MATURITY_LEVEL_PRIORITY`
- [#27](https://github.com/kobkob/K-AIDF/issues/27) - [bug] MCP leaks internal errors; `initialize` echoes arbitrary protocolVersion
- [#26](https://github.com/kobkob/K-AIDF/issues/26) - [perf] MCP re-indexes the entire repo on every request; no rate limiting
- [#25](https://github.com/kobkob/K-AIDF/issues/25) - [bug] Undocumented `content:`/`inline:` precedence; required-but-unused `spec["version"]`
- [#24](https://github.com/kobkob/K-AIDF/issues/24) - [bug] Duplicate file paths in spec silently overwrite
- [#23](https://github.com/kobkob/K-AIDF/issues/23) - [bug] Malformed YAML bypasses the generator's error taxonomy (raw traceback)
- [#22](https://github.com/kobkob/K-AIDF/issues/22) - [security] Path traversal in `template_loader.load_template_by_key`
- [#21](https://github.com/kobkob/K-AIDF/issues/21) - [docs] README "AI Controller" section documents pre-0.5.x behavior
- [#20](https://github.com/kobkob/K-AIDF/issues/20) - [cleanup] Obsolete RELEASING.md; dead `cli/main.py.old` committed in src/
- [#19](https://github.com/kobkob/K-AIDF/issues/19) - [tech-debt] Version drift: `__version__` disagrees with pyproject
- [#18](https://github.com/kobkob/K-AIDF/issues/18) - [ci] MCP CI never runs the test suite
- [#17](https://github.com/kobkob/K-AIDF/issues/17) - [ci] Generator CI is red by its own ruff rules
- [#16](https://github.com/kobkob/K-AIDF/issues/16) - [bug] `kob init`/`compile` coupled to monorepo layout; pip install at runtime
- [#15](https://github.com/kobkob/K-AIDF/issues/15) - [tech-debt] Duplicated indexing logic (agent vs MCP) is already diverging
- [#14](https://github.com/kobkob/K-AIDF/issues/14) - [security] v2 `visibility` is parsed and exposed but never enforced
- [#13](https://github.com/kobkob/K-AIDF/issues/13) - [contract] Front matter v2 missing on ~45% of generated corpus (contract vs default spec disagree)
- [#12](https://github.com/kobkob/K-AIDF/issues/12) - [content] Canonical doctrine files are empty (literal TODO. in generated output)
- [#11](https://github.com/kobkob/K-AIDF/issues/11) - [security] OAuth 2.1 with PKCE is a hardcoded-token stub; open redirector in /oauth/authorize
- [#9](https://github.com/kobkob/K-AIDF/issues/9) - Make Installation and app up
- [#8](https://github.com/kobkob/K-AIDF/issues/8) - Iterative behavior in KAIDF project
- [#7](https://github.com/kobkob/K-AIDF/issues/7) - Special repositories
- [#6](https://github.com/kobkob/K-AIDF/issues/6) - Licenses, trademarks and agreements
- [#5](https://github.com/kobkob/K-AIDF/issues/5) - The UI Embryo (Mentor Web App Runtime)
- [#4](https://github.com/kobkob/K-AIDF/issues/4) - Standardized and Graphical Terminal Output (Rich CLI)
- [#2](https://github.com/kobkob/K-AIDF/issues/2) - Implement local LLMProvider interface for offline OLMo (Ollama) inference

## Notes

- This list reflects the open issues currently visible in the GitHub repository.
- The repository may contain additional hidden/closed issues not included here.
- Source: https://github.com/kobkob/K-AIDF/issues
