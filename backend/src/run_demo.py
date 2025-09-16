from __future__ import annotations
import argparse, os, pathlib, sys
from .secure_wrapper import process_file

def main():
    ap = argparse.ArgumentParser(
        description="0PIRATE: Secure Code Fixer (BYOK + Free OSS)"
    )
    ap.add_argument("--input", required=True, help="Path to input code file")
    ap.add_argument(
        "--provider",
        default="auto",
        help="auto|openai|anthropic|gemini|deepseek|mistral|groq|ollama"
    )
    ap.add_argument("--model", default=None, help="Model name for provider")
    ap.add_argument(
        "--task",
        default="fix_and_secure",
        choices=[
            "fix_and_secure",
            "code_review",
            "documentation",
            "test_cases",
            "refactor"
        ],
        help="The task for the LLM to perform on the code."
    )
    # Changed the flag to a simple boolean and renamed it for clarity
    ap.add_argument(
        "--diff-mode",
        action="store_true", # This flag will be True if present, False otherwise
        help="If set, returns a unified diff instead of the full code."
    )
    args = ap.parse_args()

    inp = args.input
    
    # The output file name now depends on the task to avoid overwriting files
    if args.task == "documentation":
        outp = str(pathlib.Path("data/output_docs") / (pathlib.Path(inp).stem + ".md"))
    elif args.task == "code_review":
        outp = str(pathlib.Path("data/output_reviews") / (pathlib.Path(inp).stem + ".review.md"))
    else:
        outp = str(pathlib.Path("data/output_code") / (pathlib.Path(inp).stem + f".{args.task}.py"))

    # Pass the new diff-mode flag to process_file
    result = process_file(inp, provider_name=args.provider, model=args.model, task=args.task, diff_mode=args.diff_mode)
    
    # Write the output to a file
    with open(outp, "w", encoding="utf-8") as f:
        f.write(result)
    
    print(f"Task '{args.task}' completed. Output written to '{outp}'.")


if __name__ == "__main__":
    main()
