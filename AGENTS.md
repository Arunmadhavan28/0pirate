# AGENTS.md — 0Pirate repo

This repo is protected by 0Pirate zero-knowledge middleware.

## Mandatory for all agents

1. NEVER read `*.py`, `*.js`, `*.ts`, `*.java` directly with file tools.
   Call MCP `read_secure_file` instead.
2. NEVER write code files directly. Call MCP `write_secure_file` with
   placeholders intact.
3. Call `audit_status` before any external LLM call and report:
   secrets blocked / identifiers abstracted.
4. Secret placeholders look like `<<REDACTED_*_hash>>`.
   Logic placeholders look like `<<FUNC_*>>`, `<<VAR_*>>`, `<<CLASS_*>>`,
   `<<PARAM_*>>`, `<<STRING_*>>`, `<<NUM_*>>`, `<<COMMENT_*>>`.
   Do not resolve, invent, or strip them.
5. If a write fails with "call read_secure_file first", re-read — mappings
   are in-memory per server session.
6. Datasets return schema only. Binaries return base64. Both are intentional.
7. Never log or output original secrets. Audit log contains metadata only
   (`.0pirate-audit.log`).

## Local commands

```bash
python cli/mcp_server.py                                # stdio
python cli/mcp_server.py --transport streamable-http --port 8000
python -m pytest backend/tests -q                       # backend tests
python -m pytest cli/tests -q                           # fail-closed redaction tests
```

## Config

- `.0pirate.yml` (`allow_list:`) — identifiers to never abstract.
- `REDACTION_SALT`, `REDACTOR_COMPLIANCE=global|strict|gdpr|dpdpa` env vars.
