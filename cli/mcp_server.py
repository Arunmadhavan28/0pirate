import sys
import json
import logging
import asyncio
import base64
from pathlib import Path
import yaml
import datetime

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Local Zero-Knowledge Engine
from engine import run_redaction
from main import restore_code

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_server")

server = Server("0Pirate Secure Agentic Proxy")

# In-memory mapping store to restore code after the agent finishes
MAPPING_STORE = {}

def get_config(repo_root: Path) -> dict:
    config_path = repo_root / ".0pirate.yml"
    if config_path.exists():
        try:
            return yaml.safe_load(config_path.read_text()) or {}
        except Exception as e:
            logger.error(f"Failed to parse .0pirate.yml: {e}")
    return {}

def append_audit_log(repo_root: Path, action: str, details: str):
    log_path = repo_root / ".0pirate-audit.log"
    timestamp = datetime.datetime.now().isoformat()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {action} | {details}\n")
    except Exception:
        pass

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    Exposes zero-knowledge tools to the connected agent (Cursor/Claude).
    """
    return [
        types.Tool(
            name="read_secure_file",
            description="Reads a local file, runs the 0Pirate zero-knowledge abstraction engine to hide secrets and proprietary logic, and returns the safe, abstracted code to you. YOU MUST USE THIS TO READ FILES.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute or relative path to the file."}
                },
                "required": ["file_path"]
            }
        ),
        types.Tool(
            name="write_secure_file",
            description="Takes your abstracted code modifications, securely restores the original proprietary logic and secrets using local mapping tables, and writes it back to disk.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "abstracted_code": {"type": "string", "description": "The modified code still containing the abstracted placeholders (e.g., func_01, VAR_A)."}
                },
                "required": ["file_path", "abstracted_code"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if not arguments:
        raise ValueError("Missing arguments")
        
    if name == "read_secure_file":
        file_path = Path(arguments["file_path"])
        if not file_path.exists():
            return [types.TextContent(type="text", text=f"Error: File not found at {file_path}")]
            
        # 1. Image / Binary Passthrough
        # If the file is an image or binary, we cannot redact text. 
        # We pass it through directly to preserve multimodal context.
        binary_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}
        if file_path.suffix.lower() in binary_extensions:
            encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
            mime_type = f"image/{file_path.suffix.lower()[1:]}"
            if mime_type == "image/jpg": mime_type = "image/jpeg"
            return [
                types.TextContent(type="text", text=f"[System: Passed through binary file {file_path.name} unaltered to preserve context.]\nBase64Data:{encoded}")
            ]

        # 2. Sensitive Dataset Protection (HIPAA / PII)
        # LLMs do not need raw medical/financial datasets to write code. They only need the schema.
        dataset_extensions = {".csv", ".tsv", ".sql", ".db", ".sqlite", ".parquet"}
        if file_path.suffix.lower() in dataset_extensions:
            try:
                # Only read the very first line (the headers/schema)
                with open(file_path, "r", encoding="utf-8") as f:
                    schema = f.readline().strip()
                return [
                    types.TextContent(type="text", text=f"[0Pirate Security Block: Raw access to dataset '{file_path.name}' is strictly prohibited to prevent PII/HIPAA leaks. The LLM only requires the schema to write code. Here is the dataset schema/header:]\n\n{schema}")
                ]
            except Exception:
                return [types.TextContent(type="text", text=f"[0Pirate Security Block: Access to binary dataset '{file_path.name}' is strictly prohibited.]")]

        # 3. Text Redaction
        try:
            code_content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return [types.TextContent(type="text", text=f"Error: {file_path} appears to be a binary file but is not a supported image format.")]
        
        # Load custom configurations
        repo_root = file_path.parent
        while not (repo_root / ".git").exists() and repo_root != repo_root.parent:
            repo_root = repo_root.parent
        config = get_config(repo_root)
        allow_list = config.get("allow_list", [])
        
        try:
            # 100% Local Redaction. No network requests!
            files_dict = {file_path.name: code_content}
            redaction_data = run_redaction(files_dict, allow_list=allow_list)
            
            abstracted_content = redaction_data["abstracted_files"].get(file_path.name)
            
            # Save the mappings locally. They NEVER go to the LLM.
            MAPPING_STORE[str(file_path)] = {
                "secret_maps": redaction_data["secret_maps"].get(file_path.name, {}),
                "abstraction_maps": redaction_data["abstraction_maps"].get(file_path.name, {})
            }
            
            secrets_blocked = len(MAPPING_STORE[str(file_path)]["secret_maps"])
            logic_abs = len(MAPPING_STORE[str(file_path)]["abstraction_maps"])
            append_audit_log(repo_root, "READ_SECURE", f"File: {file_path.name} | Secrets Blocked: {secrets_blocked} | Logic Abstracted: {logic_abs}")
            
            return [types.TextContent(type="text", text=abstracted_content)]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error during local redaction: {str(e)}")]

    elif name == "write_secure_file":
        file_path = Path(arguments["file_path"])
        abstracted_code = arguments["abstracted_code"]
        
        mappings = MAPPING_STORE.get(str(file_path))
        if not mappings:
            return [types.TextContent(type="text", text=f"Error: Cannot write to {file_path}. You must read it with read_secure_file first to establish a local mapping table.")]
            
        try:
            # Safely restore the original secrets and logic
            final_code = restore_code(
                abstracted_code,
                mappings["secret_maps"],
                mappings["abstraction_maps"]
            )
            
            file_path.write_text(final_code, encoding="utf-8")
            
            repo_root = file_path.parent
            while not (repo_root / ".git").exists() and repo_root != repo_root.parent:
                repo_root = repo_root.parent
            append_audit_log(repo_root, "WRITE_SECURE", f"File: {file_path.name} restored successfully.")
            
            return [types.TextContent(type="text", text=f"Successfully restored and wrote to {file_path}")]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error during restoration: {str(e)}")]
            
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="0pirate-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
