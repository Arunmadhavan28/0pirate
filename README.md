<div align="center">
  <img src="https://raw.githubusercontent.com/Arunmadhavan28/0pirate/main/logo.png" alt="0Pirate Logo" width="200" />
  <h1>0Pirate</h1>
  <p>Local redaction proxy and zero-knowledge middleware for AI-assisted coding</p>
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
</div>

---

## Overview

0Pirate is a local proxy that sits between your development environment and frontier AI models. It removes credentials, replaces proprietary business logic with structural placeholders, sends the sanitized code to the AI provider, and restores the original code locally when the response arrives.

## The Problem

Engineering teams face a direct trade-off between AI coding performance and code privacy:

### 1. Local models fall short on complex code
Running local open-weight models through tools like Ollama keeps data on your machine, but smaller models (7B to 70B) cannot match the reasoning, context tracking, and multi-file refactoring abilities of frontier cloud models. For complex system design and hard bugs, local models often slow developers down.

### 2. Cloud models expose sensitive assets
Sending unredacted code to third-party endpoints creates exposure risks across three areas:
- Credentials and secrets: API keys, database connection strings, SSH keys, authentication tokens.
- Personal and infrastructure data: Internal hostnames, private IP addresses, employee emails, customer data in test fixtures.
- Intellectual property: Proprietary algorithms, financial formulas, patented logic, and domain-specific business rules.

### 3. Traditional masking tools break code
Standard data loss prevention filters and regex rules treat code like plain text:
- Regex replacements break Abstract Syntax Tree (AST) structures, scope boundaries, and language typing.
- Simple masks do not hide the semantics of proprietary logic.
- Text filters are one-way. When an AI returns a code patch, regex tools cannot automatically restore the original identifiers into working code.

## How 0Pirate Works

0Pirate runs entirely on your local machine or private network:

1. **AST-level abstraction**: Rather than using naive text replacement, 0Pirate parses the syntax tree. Proprietary functions, internal classes, and business variables are mapped to structurally valid placeholder tokens.
2. **Secret redaction**: High-entropy strings, credential formats, and sensitive constants are detected and removed before any payload is sent.
3. **Model-agnostic routing**: 0Pirate does not depend on a specific AI model. It works with any modern provider:
   - Anthropic: Claude 3.7 Sonnet, Claude 3.5 Sonnet, Claude Opus
   - OpenAI: GPT-4o, o1, o3-mini
   - DeepSeek: DeepSeek-R1, DeepSeek-V3
   - Google: Gemini 2.0 Flash, Gemini 1.5 Pro
   - Meta, Mistral, and custom endpoints via OpenRouter or OpenAI-compatible APIs
4. **Local rehydration**: When the model returns generated code or a diff, 0Pirate maps all placeholders back to your original variable names, functions, and secrets in local memory. The remote provider never receives the raw IP.

## Using with Agentic IDEs (Cursor and Claude Code)

0Pirate runs as a local Model Context Protocol (MCP) server. When an agent in Cursor or Claude Code requests project context, 0Pirate intercepts the file read, redacts the contents, and returns the safe version.

### MCP Configuration

Add 0Pirate to your Cursor or Claude Desktop configuration file:

```json
{
  "mcpServers": {
    "0pirate-secure-proxy": {
      "command": "python3",
      "args": ["/path/to/0pirate/cli/mcp_server.py"]
    }
  }
}
```

Once configured, the agent reads and writes code through the proxy without exposing your underlying secrets or proprietary identifiers.

## Quickstart

Run the local stack:

### Prerequisites
- Docker and Docker Compose
- Python 3.10 or newer

### Setup

```bash
# Clone the repository
git clone https://github.com/Arunmadhavan28/0pirate.git
cd 0pirate

# Set up environment variables
cp .env.example .env

# Start local services
docker-compose up -d

# Install CLI and pre-commit hook
cd cli
pip install -r requirements.txt
python main.py install-hook
```

Services:
- Backend proxy: http://localhost:5001
- Frontend dashboard: http://localhost:3000
- Pre-commit hook: checks git commits for accidental secret leakage

## Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md): Technical details on the AST parser, token mapping, and local storage.
- [CONTRIBUTING.md](./CONTRIBUTING.md): Contribution guidelines and local testing setup.
- [0Pirate GitHub Action](./0pirate-action/README.md): CI workflow for scanning pull requests.

## Community

- Issue tracker: [GitHub Issues](https://github.com/Arunmadhavan28/0pirate/issues)

## License

This project is licensed under the [MIT License](LICENSE).
