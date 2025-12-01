import typer
import requests
import json
import os
import hashlib
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Optional
from rich.markdown import Markdown

# Default to your live production backend
DEFAULT_BACKEND_URL = "https://backend-muddy-moon-310.fly.dev"
app = typer.Typer(help="0Pirate CLI - AI Security & Refactoring Agent")
console = Console()
CONFIG_PATH = Path.home() / ".0pirate_config.json"

def load_config():
    """Loads the JSON config file."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except:
            return {}
    return {}

def save_config(data):
    """Saves data to the JSON config file."""
    current = load_config()
    current.update(data)
    CONFIG_PATH.write_text(json.dumps(current, indent=2))

def restore_code(abstracted_code: str, secret_map: dict, abstraction_map: dict) -> str:
    """Restores original values from placeholders."""
    reverse_map = {}
    for original, placeholder in abstraction_map.items():
        reverse_map[placeholder] = original
    for placeholder, original in secret_map.items():
        reverse_map[placeholder] = original

    sorted_placeholders = sorted(reverse_map.keys(), key=len, reverse=True)
    restored = abstracted_code
    for ph in sorted_placeholders:
        restored = restored.replace(ph, reverse_map[ph])
    return restored

@app.command()
def login(
    token: str = typer.Option(..., prompt="Paste your 0Pirate Action Token (from Dashboard)", help="Your 0Pirate Auth Token"),
    llm_key: str = typer.Option(..., prompt="Paste your LLM API Key (OpenAI/Gemini)", help="Your LLM Provider Key")
):
    """
    Log in to unlock higher quotas and save your API keys.
    """
    save_config({"auth_token": token, "llm_api_key": llm_key})
    console.print(f"[green]✓ Credentials saved to {CONFIG_PATH}[/green]")
    console.print("[dim]You can now run '0pirate fix' with your account limits.[/dim]")

@app.command()
def fix(
    file_path: Path = typer.Argument(..., help="The file to fix", exists=True),
    error_log: Optional[str] = typer.Option(None, "--log", "-l", help="Optional error log/traceback"),
    output: Optional[Path] = typer.Option(None, "--out", "-o", help="Output file (defaults to stdout)"),
    backend: str = typer.Option(DEFAULT_BACKEND_URL, help="Backend URL"),
    # --- FIX START: Explicitly add these flags ---
    api_key: Optional[str] = typer.Option(None, "--api-key", help="LLM API Key (OpenAI/Gemini)"),
    auth_token: Optional[str] = typer.Option(None, "--auth-token", help="0Pirate Action Token")
    # --- FIX END ---
):
    """
    Fixes a file. Auto-detects if you are logged in or anonymous.
    """
    config = load_config()
    
    # 1. Priority: Flag > Env Var > Config File
    final_llm_key = api_key or os.getenv("PIRATE_API_KEY") or config.get("llm_api_key")
    final_auth_token = auth_token or os.getenv("PIRATE_AUTH_TOKEN") or config.get("auth_token")

    if not final_llm_key:
        console.print("[red]Error: LLM API Key not found.[/red]")
        console.print("Run `python main.py login` OR set `PIRATE_API_KEY` env var.")
        raise typer.Exit(1)
    
    code_content = file_path.read_text(encoding="utf-8")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        task_id = progress.add_task("description", total=None)
        progress.update(task_id, description="[cyan]Step 1/3: Redacting secrets...[/cyan]")
        
        try:
            # --- STEP 1: REDACT ---
            files = {'files': (file_path.name, code_content)}
            redact_res = requests.post(f"{backend}/api/redact", files=files)
            redact_res.raise_for_status()
            redaction_data = redact_res.json()
            
            abstracted_content = redaction_data["abstracted_files"].get(file_path.name)
            
            # --- STEP 2: PROCESS ---
            progress.update(task_id, description="[cyan]Step 2/3: Running 0pirate Agent...[/cyan]")
            
            sha = hashlib.sha256(abstracted_content.encode("utf-8")).hexdigest()
            
            payload = {
                "task": "fix_and_secure",
                "provider": "gemini", 
                "model": "gemini-2.5-pro",
                "api_key": final_llm_key, # Use the resolved key
                "token_saver_enabled": "false",
                "cove_hardening_enabled": "true",
                "tamper_evident_hash": sha,
                "error_log": error_log or ""
            }
            
            # Headers: Send Auth Token if we have it
            headers = {}
            if final_auth_token:
                headers["X-0Pirate-Action-Token"] = final_auth_token
            
            files_payload = [('files', (file_path.name, abstracted_content))]
            
            process_res = requests.post(
                f"{backend}/api/process_code", 
                data=payload, 
                files=files_payload,
                headers=headers # <--- THIS UNLOCKS THE QUOTA
            )
            
            if process_res.status_code == 429:
                console.print("[red]Quota Exceeded.[/red] Run `python main.py login` to upgrade limits.")
                raise typer.Exit(1)
                
            process_res.raise_for_status()
            job_id = process_res.json()["job_id"]
            
            # --- STEP 3: POLL ---
            import time
            while True:
                # We also send headers here so status check is authorized
                status_res = requests.get(f"{backend}/api/status/{job_id}", headers=headers)
                if status_res.status_code != 200:
                    continue
                
                job_data = status_res.json()
                status = job_data.get("status")
                if status in ["completed", "failed"]:
                    break
                time.sleep(1)
            
            if status == "failed":
                console.print(f"[red]Job Failed:[/red] {job_data.get('notice')}")
                raise typer.Exit(1)

            # --- STEP 4: RESTORE ---
            progress.update(task_id, description="[green]Finalizing...[/green]")
            
            result_data = job_data.get("result", {})
            if isinstance(result_data, str):
                try: result_data = json.loads(result_data)
                except: pass
            
            raw_fixed_code = result_data.get(file_path.name, "") if isinstance(result_data, dict) else str(result_data)

            final_code = restore_code(
                raw_fixed_code, 
                redaction_data["secret_maps"].get(file_path.name, {}), 
                redaction_data["abstraction_maps"].get(file_path.name, {})
            )
            
            progress.stop()
            console.rule("[bold green]Analysis Complete[/bold green]")

            server_notice = job_data.get("notice")
            if server_notice:
                console.print(f"[bold blue]Server Message:[/bold blue] {server_notice}")
            
            analysis = job_data.get("analysis")
            if analysis:
                 console.rule("[bold blue]AI Analysis[/bold blue]")
                 console.print(Markdown(analysis))
                 console.print("\n")
            
            sb_res = job_data.get("sandbox_result", {})
            if sb_res and sb_res.get("status") == "success":
                console.print("[bold green]✅ Sandbox Verification Passed[/bold green]")
            elif sb_res:
                console.print(f"[bold yellow]⚠️ Sandbox Status: {sb_res.get('status')}[/bold yellow]")

            if output:
                output.write_text(final_code, encoding="utf-8")
                console.print(f"Fixed code saved to: [bold]{output}[/bold]")
            else:
                console.print(final_code)

        except Exception as e:
            progress.stop()
            console.print(f"[red]Error:[/red] {e}")

if __name__ == "__main__":
    app()