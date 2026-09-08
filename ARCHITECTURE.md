# 0Pirate Architecture

0Pirate operates on a simple principle: **Never send raw proprietary code to an LLM.**

To achieve this, the system is split into two primary domains: The **Client-Side Redactor** and the **Backend Proxy**.

## The Flow

1. **Client Submission:** The developer (via CLI or GitHub Action) triggers an AI code generation request on their local files.
2. **Local Redaction (`client_redactor.py`):** 
   - A highly optimized Regex Engine strips known secrets (API Keys, tokens, passwords).
   - An NLP pass (if enabled) removes PII (names, emails).
   - An Abstraction Engine replaces proprietary identifiers (e.g., `process_stripe_payment`) with generic placeholders (e.g., `func_01`).
3. **Mapping Table:** The client keeps a local mapping table (`"func_01" -> "process_stripe_payment"`) and **does not** send it to the backend.
4. **Proxy Request:** The abstracted, safe code is sent to the 0Pirate backend (`api/routes/jobs.py`).
5. **LLM Generation:** The backend routes the safe code to the requested provider (OpenAI, Anthropic, Ollama). The LLM processes the code and generates a response using the abstracted tokens.
6. **Reconstitution:** The backend returns the abstracted response. The local client uses its mapping table to reverse the abstraction, restoring the original identifiers before saving the file to disk.

## Directory Structure

```text
0pirate/
├── backend/                  # Fast API Server
│   ├── src/
│   │   ├── api/              # Modular API Routes (Jobs, Auth, Billing)
│   │   ├── providers/        # LLM SDK Integrations (OpenAI, Anthropic, etc.)
│   │   ├── sandbox.py        # Isolated Docker runtime for verifying code
│   │   ├── redactor.py       # Core regex and NLP redaction logic
│   │   └── abstractor.py     # AST-based code abstraction logic
│   └── tests/                # Pytest unit and integration tests
├── frontend/                 # Next.js Dashboard
├── cli/                      # Command Line Interface tool
└── 0pirate-action/           # Standalone GitHub Action for secure PR reviews
```

## Security Guarantees
- **No Persistence:** Abstracted code sent to the 0Pirate backend is processed entirely in memory. It is not saved to the database unless explicitly requested for telemetry.
- **Sandboxing (COVE):** When COVE hardening is enabled, AI-generated code is executed inside a heavily restricted, network-isolated Docker container to ensure it does not contain malicious behavior before being returned to the user.
