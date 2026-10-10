---
name: 0pirate-secure-coding
description: Read and write code through the 0Pirate zero-knowledge proxy so secrets and proprietary logic never reach the LLM. Use when touching any repo file that may contain credentials, PII, or IP.
version: 0.2.0
---

# 0Pirate Secure Coding Skill

You are operating in a repo protected by 0Pirate. NEVER read project code
files directly. Route every read/write through the MCP tools.

## Workflow

1. **Read**: `read_secure_file(file_path="<path>")`
   Returns abstracted code with `<<REDACTED_*>>` and `<<FUNC_*>>` /
   `<<VAR_*>>` / `<<CLASS_*>>` placeholders. Keep them intact.
2. **Audit**: `audit_status(file_path="<path>")`
   Report counts to the user before sending anything to a model.
3. **Edit**: work only on the abstracted text.
4. **Write**: `write_secure_file(file_path="<path>", abstracted_code="<edited>")`
   The proxy restores originals locally. Never invent placeholders.
5. **Verify**: `audit_status()` for a session summary.

## Rules

- If `write_secure_file` says "call read_secure_file first", do so — the
  mapping table is per-session and local-only.
- Datasets (`.csv/.sql/.parquet`): you only get the schema. That's enough.
- Binary files: passed through as base64, do not redact.
- Never print or exfiltrate placeholder mappings. They stay local.
- For compliance questions, read the `pirate://audit-log` resource.

## Example

```
read_secure_file(file_path="src/auth.py")
audit_status(file_path="src/auth.py")
# ... edit abstracted code ...
write_secure_file(file_path="src/auth.py", abstracted_code="...")
```
