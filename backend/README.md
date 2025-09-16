
# Project 0PIRATE: Secure, AI‑Powered Code Optimization (BYOK + Privacy)

0PIRATE is a secure pipeline that fixes buggy code with AI while protecting secrets.
- **BYOK**: Users can plug in their own API keys (OpenAI, Anthropic, Gemini, DeepSeek, Mistral, Groq).
- **Free tier**: Uses **Ollama** locally (e.g., `llama3.1:8b`, `mistral`) for zero‑cost private inference.
- **Security**: Secrets are **redacted** before leaving your machine and restored **locally** from an encrypted vault.

## Quick Start

### 1) Install requirements
```bash
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2) (Optional) Install & run Ollama (for free tier)
- Install from https://ollama.com
- Pull a small model: `ollama pull mistral`
- Ensure the daemon is running: `ollama serve` (usually auto)

### 3) Provide API keys (BYOK)
Set environment variables as needed:
```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...        # Gemini
DEEPSEEK_API_KEY=...
MISTRAL_API_KEY=...
GROQ_API_KEY=...
```
Keys are **optional**. If none are provided, 0PIRATE will use **Ollama** (if available) for the free tier.

### 4) Put buggy code into `data/input_code/`
Example: `data/input_code/code.py`

### 5) Run
```bash
python -m src.run_demo --input data/input_code/code.py --provider auto --model mistral
```
- `--provider` can be: `auto|openai|anthropic|gemini|deepseek|mistral|groq|ollama`
- `--model` depends on provider (e.g., `gpt-4o-mini` for OpenAI, `claude-3-haiku-20240307` for Anthropic, `mistral` for Ollama).

The fixed code will be written to `data/output_code/code.fixed.py`.

## Security Workflow

1. **Redaction**: Replace secrets with placeholders like `<API_KEY_1>`, store mapping in encrypted vault.
2. **Send to LLM**: Only sanitized code is sent to the selected provider (or to local Ollama).
3. **Reconstruction**: Restore secrets locally using the vault (never leaves your machine).

## Routing strategy (auto)
- If any paid API keys are available, route to the **best model** by task type (basic example provided).
- Otherwise, fallback to **Ollama** free local model.

## Disclaimer
This is a sample MVP for educational purposes; audit before production.
