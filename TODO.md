# TODO — odoo-mcp

## Em curso

_(nada)_

## Pendente

- Investigar bug `account` module Odoo 16 (db `odoo-steriliza-teste`): `_credit_debit_get` gera `AND account_move_line.partner_id IN ()` em `default_get`/`onchange` para partner novo sem id. Quebra `test_default_get_returns_dict` e `test_onchange_company_type` no smoke live (8/10 pass). Tools MCP correctas — bug no servidor. Opcoes: guard XML-RPC fault no impl, xfail testes, ou validar contra DB com account patched.
- Pipe `odoo_execute_kw` aceitar args/kwargs aninhados complexos (validar)
- Publicar marketplace: criar `.claude-plugin/marketplace.json` se for partilhado
- Segunda onda: testes pytest + CI, `ODOO_READ_ONLY` env flag, `unlink` dry-run, TTL cache em `fields_get`
- Subagente `odoo-analyst` (read-only) e skill `odoo-domain` (DSL e operadores)
- Migrar `.mcp.json` actual para perfil nomeado e remover creds hardcoded do JSON

## Feito

- 2026-05-09 — Suporte JSON-RPC por perfil: campo `transport` em `profiles.set_profile`/`get_profile`/`list_profiles` (`xmlrpc`|`jsonrpc`, default `xmlrpc`); modulo `_jsonrpc.py` (stdlib `urllib.request`); `transport.connect()` + `exec_kw` despacham pelo `transport` do perfil; `odoo_add_profile` aceita `transport_flag`; verificado live contra `oximed-prod` (uid=2) que falha por bug `website` XML-RPC — JSON-RPC bypass funciona.

- 2026-05-09 — Smoke live executado contra novo profile `odoo-steriliza-teste` (URL `http://vps46593.publiccloud.com.br/`, Odoo 16.0): 8/10 pass. 2 falhas (`test_default_get_returns_dict`, `test_onchange_company_type`) sao bug do `account` module no servidor (SQL `IN ()` vazio em `_credit_debit_get`), nao regressao MCP. Default gate intacto (44 unit pass + 10 skip). Issue logada em Pendente.

- 2026-05-09 — Fase 1 foundation tools: refactor `server.py` em modulos (`transport.py`, `_helpers.py`, `tools/{auth,crud,discovery,inspection,workflow}.py`); 11 tools novas (`odoo_metadata`, `odoo_view_get`, `odoo_menu_tree`, `odoo_modules_list`, `odoo_access_check`, `odoo_user_groups`, `odoo_company_list`, `odoo_call_button`, `odoo_onchange`, `odoo_default_get`, `odoo_copy`); `pytest` + tests unit (44) + smoke integration (10 testes live, gate `ODOO_TEST_LIVE=1`).

- 2026-05-07 — Hook `SessionStart` auto-mata zombies do MCP server (parent dead) via `scripts/mcp-zombies.ps1` (flags `-Kill -Quiet`). Detecta `odoo-mcp.exe` + `python.exe` do `.venv` + `uv.exe` ligados a `odoo-mcp`. Zombies = pai morto (sessao Claude antiga); IN-USE = pai vivo (nao tocado). Resolveu MCP error -32000 "Connection closed" causado por lock de `odoo-mcp.exe` em reinstall do uv.

- 2026-05-07 — Multi-instancia: profiles nomeados em `~/.claude/odoo-mcp.profiles.json`, passwords no OS keyring (Windows Credential Manager / macOS Keychain / libsecret) com fallback para ficheiro chmod 600 se keyring indisponivel. Tools novos: `odoo_list_profiles`, `odoo_current_profile`, `odoo_add_profile`, `odoo_use_profile`, `odoo_remove_profile`, `odoo_connect_ad_hoc`, `odoo_test_connection`. Slash commands `/odoo-mcp:setup` (refeito p/ profiles), `/odoo-mcp:profiles`, `/odoo-mcp:use [name]`, `/odoo-mcp:connect`. Cache de auth por-profile (switch sem re-auth). Retrocompat: env vars expostas como profile virtual `_env`.

- 2026-05-07 — Slash command `/odoo-mcp:setup` (interactive credential collection, writes `~/.claude/odoo-mcp.env`); server self-loads esse ficheiro no arranque (precedência: env existente > ficheiro; valores vazios em env tratados como ausentes)
- 2026-05-06 — Primeira onda de melhorias: fix `odoo_list_models` (param `pattern` + alias `filter`/`filter_name`, paginação, default 100), `odoo_fields_get(business_only=True)` filtra mixins (activity_/message_/website_message_/_count/...), nova tool `odoo_multi_field_search`, `odoo_resolve_xmlid`, `odoo_chatter_read` (strip HTML)
- 2026-05-06 — Confiabilidade: timeout XML-RPC (`ODOO_TIMEOUT`, default 30s), retry 3x com backoff em erros transitórios, re-auth automático em `AccessDenied`/`Session expired`, logging stderr (`ODOO_LOG_LEVEL`)
- 2026-05-06 — Slash commands `/odoo:find <model> <term>` e `/odoo:schema <model>`
- 2026-05-06 — Smoke test 11/11 contra Odoo 16 local (db `odoo-steriliza`): auth, list_models, fields_get, search_count, search_read, create+read+write+read+unlink+count round-trip em `res.partner`
- 2026-05-06 — Scaffold inicial do plugin (`.claude-plugin/plugin.json`, `.mcp.json`)
- 2026-05-06 — Servidor Python MCP com 11 tools (search/read/create/write/unlink/...)
- 2026-05-06 — `pyproject.toml` + entry point `odoo-mcp`
- 2026-05-06 — README, .env.example, .gitignore
