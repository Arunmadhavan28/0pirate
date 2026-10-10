"""0Pirate Secure Agentic Proxy — MCP server (SDK v2).

Exposes zero-knowledge file tools to any MCP client
(Cursor, Claude Code, VS Code, Windsurf, custom agents).

Transports:
  stdio (default, local):   python mcp_server.py
  streamable-http (hosted): python mcp_server.py --transport streamable-http --port 8000

Tools (discover via tools/list, invoke via tools/call):
  read_secure_file  — read + redact + abstract, returns safe code
  write_secure_file — rehydrate placeholders + write to disk
  audit_status      — prove what was blocked, without leaking secrets
"""

from __future__ import annotations

import argparse
import base64
import datetime
import logging
from pathlib import Path
from typing import Optional

import yaml

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from engine import run_redaction
from abstractor import AbstractionFailed
from main import restore_code

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("0pirate-mcp")

server = MCPServer(
    name="0pirate-secure-proxy",
    title="0Pirate Secure Proxy",
    version="0.2.0",
    description=(
        "Local zero-knowledge proxy for AI coding. "
        "Reads files, strips secrets/PII and abstracts proprietary logic "
        "before the LLM ever sees them, then restores originals locally on write."
    ),
    instructions=(
        "SECURITY POLICY: To read any code file, call read_secure_file — "
        "never read project files directly. "
        "To save agent-edited code, call write_secure_file with the "
        "abstracted placeholders intact. "
        "Call audit_status to verify what was blocked."
    ),
)

# In-memory mapping store. Secrets NEVER leave this process.
MAPPING_STORE: dict[str, dict] = {}


def get_config(repo_root: Path) -> dict:
    config_path = repo_root / ".0pirate.yml"
    if config_path.exists():
        try:
            return yaml.safe_load(config_path.read_text()) or {}
        except Exception as e:
            logger.error(f"Failed to parse .0pirate.yml: {e}")
    return {}


def find_repo_root(start: Path) -> Path:
    repo_root = start if start.is_dir() else start.parent
    while not (repo_root / ".git").exists() and repo_root != repo_root.parent:
        repo_root = repo_root.parent
    return repo_root


def append_audit_log(repo_root: Path, action: str, details: str) -> None:
    log_path = repo_root / ".0pirate-audit.log"
    timestamp = datetime.datetime.now().isoformat()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {action} | {details}\n")
    except Exception:
        pass


BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}
DATASET_EXTENSIONS = {".csv", ".tsv", ".sql", ".db", ".sqlite", ".parquet"}


@server.tool(
    description=(
        "SECURE READ — use this INSTEAD of reading code files directly. "
        "Reads a local file, strips secrets/PII (API keys, emails, IPs, "
        "high-entropy strings) and abstracts proprietary identifiers "
        "to placeholders, then returns the SAFE code. "
        "Use when: you need context from any .py/.js/.ts/.java file before "
        "editing, reviewing, or debugging it. "
        "Do NOT use for images (passed through) or datasets (schema only). "
        "Example: read_secure_file(file_path='src/auth.py'). "
        "You MUST pass the returned placeholders through unchanged to "
        "write_secure_file."
    ),
    annotations=ToolAnnotations(
        title="Secure read",
        read_only_hint=True,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
def read_secure_file(file_path: str) -> str:
    path = Path(file_path).expanduser()
    if not path.exists():
        return f"Error: File not found at {path}"

    # 1. Binary / image passthrough (preserve multimodal context)
    if path.suffix.lower() in BINARY_EXTENSIONS:
        try:
            encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        except Exception as e:
            return f"Error reading binary file: {e}"
        return (
            f"[0Pirate: binary file '{path.name}' passed through unaltered "
            f"to preserve context.]\nBase64Data:{encoded}"
        )

    # 2. Dataset protection — schema only, never raw rows
    if path.suffix.lower() in DATASET_EXTENSIONS:
        try:
            with open(path, "r", encoding="utf-8") as f:
                schema = f.readline().strip()
            return (
                f"[0Pirate Security Block: raw dataset '{path.name}' withheld "
                f"to prevent PII/HIPAA leaks. Schema/header only:]\n\n{schema}"
            )
        except Exception:
            return (
                f"[0Pirate Security Block: access to dataset "
                f"'{path.name}' is prohibited.]"
            )

    # 3. Text redaction (100% local, no network)
    try:
        code_content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: {path} appears to be binary and is not a supported format."

    repo_root = find_repo_root(path.resolve())
    config = get_config(repo_root)
    allow_list = config.get("allow_list", [])

    try:
        redaction_data = run_redaction({path.name: code_content}, allow_list=allow_list)
        abstracted = redaction_data["abstracted_files"].get(path.name, "")
        key = str(path.resolve())
        MAPPING_STORE[key] = {
            "secret_maps": redaction_data["secret_maps"].get(path.name, {}),
            "abstraction_maps": redaction_data["abstraction_maps"].get(path.name, {}),
            "file_name": path.name,
        }
        n_secrets = len(MAPPING_STORE[key]["secret_maps"])
        n_logic = len(MAPPING_STORE[key]["abstraction_maps"])
        append_audit_log(
            repo_root, "READ_SECURE",
            f"File: {path.name} | Secrets Blocked: {n_secrets} | Logic Abstracted: {n_logic}",
        )
        header = (
            f"[0Pirate: {n_secrets} secret(s) redacted, "
            f"{n_logic} identifier(s) abstracted. "
            f"Keep placeholders intact when editing.]\n\n"
        )
        return header + abstracted
    except AbstractionFailed as e:
        # Fail closed and say so: the file cannot be proven safe (parse
        # failure or surviving identifiers/secrets), so nothing is returned
        # to the model. Fix the syntax or narrow the allow_list, then retry.
        append_audit_log(repo_root, "READ_BLOCKED_UNSAFE", f"File: {path.name} | Reason: {e}")
        return (
            f"[0Pirate Security Block: '{path.name}' was NOT sent to the model. "
            f"It cannot be safely abstracted ({e}). No content from this file "
            f"has left your machine.]"
        )
    except Exception as e:
        logger.exception("redaction failed")
        return f"Error during local redaction: {e}"


@server.tool(
    description=(
        "SECURE WRITE — use this to save agent-edited code. "
        "Takes code that still contains 0Pirate placeholders "
        "(e.g. <<REDACTED_STRIPE_KEY_ab12cd34>>, <<FUNC_a1b2c3>>) and "
        "restores original secrets/logic from the LOCAL mapping table, "
        "then writes to disk. "
        "Use when: you have finished editing code obtained via "
        "read_secure_file. "
        "Prerequisite: you MUST call read_secure_file on the same path "
        "first in this session. Do NOT invent placeholders. "
        "Example: write_secure_file(file_path='src/auth.py', "
        "abstracted_code='... edited code with placeholders ...')."
    ),
    annotations=ToolAnnotations(
        title="Secure write",
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=False,
        open_world_hint=False,
    ),
)
def write_secure_file(file_path: str, abstracted_code: str) -> str:
    path = Path(file_path).expanduser()
    key = str(path.resolve())
    mappings = MAPPING_STORE.get(key) or MAPPING_STORE.get(str(path))
    if not mappings:
        return (
            f"Error: no local mapping for {file_path}. "
            f"Call read_secure_file on this path first to establish "
            f"the mapping table."
        )
    try:
        final_code = restore_code(
            abstracted_code,
            mappings["secret_maps"],
            mappings["abstraction_maps"],
        )
        path.write_text(final_code, encoding="utf-8")
        repo_root = find_repo_root(path.resolve())
        append_audit_log(repo_root, "WRITE_SECURE", f"File: {path.name} restored successfully.")
        return f"Successfully restored and wrote to {path}"
    except Exception as e:
        logger.exception("restore failed")
        return f"Error during restoration: {e}"


@server.tool(
    description=(
        "AUDIT STATUS — prove privacy without leaking secrets. "
        "Returns counts of blocked secrets and abstracted identifiers, "
        "plus recent audit-log lines (metadata only, never secret values). "
        "Use when: user asks 'what did you hide?', for compliance checks, "
        "or before sending anything to an LLM. "
        "Example: audit_status() for session summary, "
        "audit_status(file_path='src/auth.py') for one file."
    ),
    annotations=ToolAnnotations(
        title="Audit status",
        read_only_hint=True,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
def audit_status(file_path: Optional[str] = None) -> str:
    lines: list[str] = []
    if file_path:
        key_variants = [str(Path(file_path).expanduser().resolve()), file_path]
        found = next((MAPPING_STORE[k] for k in key_variants if k in MAPPING_STORE), None)
        if not found:
            return f"No session mappings for {file_path} yet. Call read_secure_file first."
        lines.append(
            f"File: {found.get('file_name', file_path)} | "
            f"Secrets blocked: {len(found['secret_maps'])} | "
            f"Identifiers abstracted: {len(found['abstraction_maps'])}"
        )
    else:
        total_secrets = sum(len(v["secret_maps"]) for v in MAPPING_STORE.values())
        total_logic = sum(len(v["abstraction_maps"]) for v in MAPPING_STORE.values())
        lines.append(
            f"Session: {len(MAPPING_STORE)} file(s) | "
            f"Secrets blocked: {total_secrets} | "
            f"Identifiers abstracted: {total_logic}"
        )
        for k, v in MAPPING_STORE.items():
            lines.append(
                f" - {v.get('file_name', k)}: "
                f"{len(v['secret_maps'])} secrets, "
                f"{len(v['abstraction_maps'])} identifiers"
            )

    # Append recent audit-log tail (metadata only)
    try:
        anchor = Path(file_path).expanduser() if file_path else Path.cwd()
        repo_root = find_repo_root(anchor.resolve())
        log_path = repo_root / ".0pirate-audit.log"
        if log_path.exists():
            tail = log_path.read_text(encoding="utf-8").splitlines()[-5:]
            lines.append("Recent audit log:")
            lines.extend(f"  {t}" for t in tail)
    except Exception:
        pass
    return "\n".join(lines)


@server.resource(
    "pirate://audit-log",
    description="Recent 0Pirate audit events (metadata only, never secret values).",
    mime_type="text/plain",
)
def audit_log_resource() -> str:
    try:
        repo_root = find_repo_root(Path.cwd().resolve())
        log_path = repo_root / ".0pirate-audit.log"
        if not log_path.exists():
            return "No audit events yet in this repository."
        return "\n".join(log_path.read_text(encoding="utf-8").splitlines()[-50:])
    except Exception as e:
        return f"Unable to read audit log: {e}"


@server.prompt(
    description="Guided secure-review workflow: read via proxy, audit, then propose a patch."
)
def secure_review(target: str) -> str:
    return (
        f"Perform a secure review of '{target}':\n"
        f"1. Call read_secure_file(file_path='{target}') — never read it directly.\n"
        f"2. Call audit_status(file_path='{target}') and report counts.\n"
        f"3. Analyze ONLY the abstracted code for bugs/secrets mishandling.\n"
        f"4. Return a patch that keeps all <<PLACEHOLDERS>> intact, "
        f"suitable for write_secure_file."
    )


@server.custom_route("/health", methods=["GET"])
async def health_check(request):  # type: ignore[no-untyped-def]
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok", "server": "0pirate-secure-proxy", "version": "0.2.0"})


def main() -> None:
    parser = argparse.ArgumentParser(description="0Pirate MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport (default: stdio for local agents)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host (streamable-http/sse)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (streamable-http/sse)")
    args = parser.parse_args()

    if args.transport == "stdio":
        server.run(transport="stdio")
    elif args.transport == "sse":
        server.run(transport="sse", host=args.host, port=args.port)
    else:
        server.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
