# Contributing to 0Pirate

First off, thank you for considering contributing to 0Pirate! It's people like you that make open-source such a great community.

## 🛠️ Development Setup

Getting started is easy. We use standard Python tooling and Docker.

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/0pirate.git
cd 0pirate
```

### 2. Backend Setup
We use `pytest` for testing and `uvicorn` for running the server.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the tests to ensure everything is working
pytest tests/
```

### 3. Frontend Setup
We use Next.js for the dashboard.

```bash
cd frontend
npm install
npm run dev
```

## 📝 Pull Request Process

1. **Fork the repo** and create your branch from `main`.
2. **Write tests:** If you are adding a new redaction feature, you *must* add a test to `backend/tests/test_redactor.py`.
3. **Run the tests:** Ensure `pytest tests/` passes completely.
4. **Format your code:** Ensure your code is clean and adheres to standard PEP8 formatting.
5. **Describe your changes:** In your PR description, clearly outline what you changed and why. If it fixes an issue, link to the issue.

## 🐞 Reporting Bugs

If you find a security flaw or a redaction bypass, **please do not open a public issue.** Email us directly at security@yourdomain.com.

For general bugs (UI glitches, CLI errors), please use the GitHub Issue tracker and provide steps to reproduce.
