<div align="center">
  <img src="https://raw.githubusercontent.com/Arunmadhavan28/0pirate/main/logo.png" alt="0Pirate Logo" width="200" />
  <h1>0Pirate</h1>
  <p><b>The Zero-Knowledge AI Proxy for Enterprise Code</b></p>
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
</div>

---

## 🏴‍☠️ Developers love AI. InfoSec hates it.

Copilot and Cursor send your proprietary code, PII, and API keys directly to third-party servers. For many enterprises, this is an unacceptable security risk. 

**"Why not just use a local LLM like Ollama?"**
Because local 8B models cannot compete with the coding intelligence of Claude 3.5 Sonnet or GPT-4o. If you use a local model, you sacrifice intelligence for privacy.

**0Pirate is the solution.**

0Pirate is an open-source, local-first redaction proxy. It sits between your codebase and frontier LLMs. Before a single line of code leaves your machine, 0Pirate **abstracts proprietary logic and redacts secrets**. The AI only sees generic placeholder variables. Once the AI returns a generated solution, 0Pirate reverses the abstraction locally.

**You get the intelligence of Claude 3.5 Sonnet with the privacy of a local LLM.**

## ✨ Features

- 🛡️ **Client-Side Redaction:** Secrets (AWS keys, passwords) and PII (emails, phone numbers) never leave your machine.
- 🧩 **Abstracted Logic:** Proprietary function names (`calculate_black_scholes_margin()`) are mapped to generic tokens (`func_A()`) before hitting the LLM.
- ⚡ **Multi-Model Support:** Plug in OpenAI, Anthropic, Google Gemini, DeepSeek.
- 🤖 **Agentic Integration (Cursor / Claude Code):** Expose 0Pirate as an MCP Server directly inside your favorite IDE.
- 📦 **GitHub Action & Pre-Commit Hooks:** Automatically review Pull Requests and local commits with Zero-Knowledge security.
- 🔒 **COVE Hardening (Optional):** Run generated code in an isolated Docker sandbox before accepting it.

## 🤖 The Agentic Era: Use with Cursor & Claude

Don't want to use our CLI? You don't have to. 0Pirate natively integrates with agentic IDEs like **Cursor** and **Claude Code** via the Model Context Protocol (MCP).

By adding 0Pirate as an MCP Server, you force your AI Agent to operate inside a zero-knowledge sandbox. When Cursor tries to read your code, 0Pirate intercepts the read, redacts it, and hands Cursor the safe version. 

### Setting up the MCP Server
```bash
# Add to your cursor/claude config:
{
  "mcpServers": {
    "0pirate-secure-proxy": {
      "command": "python3",
      "args": ["/path/to/0pirate/cli/mcp_server.py"]
    }
  }
}
```
*Now, whenever you tell Cursor to refactor a file, it will use 0Pirate's `read_secure_file` tool automatically!*

## 🚀 Quickstart (The 1-Minute Rule)

Get the entire 0Pirate stack running locally in under 60 seconds.

### Prerequisites
- Docker and Docker Compose
- Python 3.10+

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/Arunmadhavan28/0pirate.git
cd 0pirate

# 2. Set up your environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY or ANTHROPIC_API_KEY

# 3. Start the engine
docker-compose up -d

# 4. Install the CLI & Git Hook
cd cli
pip install -r requirements.txt
python main.py install-hook
```

That's it. 
- The backend is running on `http://localhost:5001`.
- The frontend dashboard is available at `http://localhost:3000`.
- Every local `git commit` is now silently audited for secrets!

## 📚 Documentation

Dive deeper into how 0Pirate achieves Zero-Knowledge AI coding:

- [**ARCHITECTURE.md**](./ARCHITECTURE.md): Understand the mapping engine and sandboxing system.
- [**CONTRIBUTING.md**](./CONTRIBUTING.md): Learn how to set up your dev environment and submit PRs.
- [**0Pirate GitHub Action**](./0pirate-action/README.md): Automate secure PR reviews.

## 🤝 Community & Support

- Report issues and request features on our [GitHub Issues](https://github.com/Arunmadhavan28/0pirate/issues) page.

## 📄 License

0Pirate is open-source software licensed under the [MIT License](LICENSE).
