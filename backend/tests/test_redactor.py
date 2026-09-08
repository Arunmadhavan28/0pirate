import pytest
from src.client_redactor import run_redaction

def test_run_redaction_removes_secrets():
    # Setup: Some code containing an email address (PII)
    input_code = {
        "main.py": "AUTHOR_EMAIL = 'admin@example.com'\ndef get_email():\n    return AUTHOR_EMAIL"
    }
    
    # Execute
    result = run_redaction(project_files=input_code)
    
    # Assert
    abstracted_files = result.get("abstracted_files", {})
    secret_maps = result.get("secret_maps", {})
    
    assert "main.py" in abstracted_files
    
    # The secret should NOT be in the output abstracted code
    assert "admin@example.com" not in abstracted_files["main.py"]
    
    # The secret MUST be in the secret map so it can be restored later
    assert "main.py" in secret_maps
    assert "admin@example.com" in secret_maps["main.py"].values()

def test_run_redaction_abstracts_logic():
    # Setup: Simple proprietary logic
    input_code = {
        "utils.py": "def calculate_proprietary_metric(user_data):\n    return user_data * 42"
    }
    
    # Execute
    result = run_redaction(project_files=input_code)
    
    # Assert
    abstracted_files = result.get("abstracted_files", {})
    abstraction_maps = result.get("abstraction_maps", {})
    
    # The proprietary function name should be gone
    assert "calculate_proprietary_metric" not in abstracted_files["utils.py"]
    
    # But it should be stored in the abstraction map for restoration
    assert "calculate_proprietary_metric" in abstraction_maps["utils.py"]
