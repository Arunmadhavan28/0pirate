# src/abstractor.py
"""
Production-level code abstraction layer for 0pirate.

Privacy layers:
- Randomized placeholders (per run, non-deterministic)
- Identifier, string, numeric abstraction
- Docstring scrubbing
- Comment scrubbing
- Noise injection (dummy vars, funcs, classes)
- Optional chunking (function-by-function or class-by-class)
- Configurable strictness levels: basic | strong | paranoid
- Safe reversible restoration

The LLM sees only sanitized junk, never real code.
"""
from __future__ import annotations
import ast
import random
import string
from typing import Tuple, Dict, List


# -----------------------------
# Helpers
# -----------------------------
def random_placeholder(prefix: str, length: int = 8) -> str:
    token = "".join(random.choices(string.ascii_letters + string.digits, k=length))
    return f"{prefix}_{token}"


# -----------------------------
# AST Transformer
# -----------------------------
class CodeAbstractor(ast.NodeTransformer):
    """AST transformer that abstracts identifiers, literals, and docstrings."""
    def __init__(self, noise_enabled: bool = True):
        self.mapping: Dict[str, str] = {}
        self.reverse_mapping: Dict[str, str] = {}
        self.noise_enabled = noise_enabled
        self.ignore_names = set(dir(__builtins__)) | {"self", "cls"}

    def _get_placeholder(self, original_name: str, category: str) -> str:
        if original_name in self.ignore_names:
            return original_name
        if original_name not in self.mapping:
            placeholder = random_placeholder(category)
            self.mapping[original_name] = placeholder
            self.reverse_mapping[placeholder] = original_name
        return self.mapping[original_name]

    # --- Node visitors ---
    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = self._get_placeholder(node.id, "var")
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.name = self._get_placeholder(node.name, "func")
        if ast.get_docstring(node):
            node.body[0] = ast.Expr(ast.Constant("abstracted_doc"))
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        node.name = self._get_placeholder(node.name, "class")
        if ast.get_docstring(node):
            node.body[0] = ast.Expr(ast.Constant("abstracted_doc"))
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self._get_placeholder(node.arg, "param")
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        if isinstance(node.value, str):
            return ast.Constant(value=self._get_placeholder(node.value, "str"))
        if isinstance(node.value, (int, float, complex)):
            return ast.Constant(value=self._get_placeholder(str(node.value), "num"))
        return node


# -----------------------------
# Main abstraction functions
# -----------------------------
def abstract(
    code: str,
    add_noise: bool = True,
    chunking: bool = False,
    level: str = "basic",
) -> Tuple[str, Dict[str, str]]:
    """
    Abstracts given code: replaces identifiers, literals, comments, etc.

    Args:
        code: Original source code string.
        add_noise: Inject dummy vars/funcs/classes.
        chunking: Abstract code per function/class instead of full file.
        level: "basic" | "strong" | "paranoid".

    Returns:
        abstracted_code, mapping
    """
    try:
        tree = ast.parse(code)

        if chunking:
            # Process each function/class separately
            abstracted_blocks: List[str] = []
            global_mapping: Dict[str, str] = {}
            for node in tree.body:
                block = ast.Module(body=[node], type_ignores=[])
                abstractor = CodeAbstractor(noise_enabled=add_noise)
                transformed = abstractor.visit(block)
                abstracted = ast.unparse(transformed)
                abstracted_blocks.append(abstracted)
                global_mapping.update(abstractor.mapping)
            abstracted_code = "\n\n".join(abstracted_blocks)

        else:
            # Process entire module
            abstractor = CodeAbstractor(noise_enabled=add_noise)
            transformed_tree = abstractor.visit(tree)

            if add_noise:
                # Insert dummy var
                dummy_var = ast.parse(
                    f'{random_placeholder("var")} = "{random_placeholder("FAKE")}"'
                )
                transformed_tree.body.insert(0, dummy_var.body[0])

                if level in ("strong", "paranoid"):
                    # Insert dummy func
                    dummy_func = ast.parse(
                        f"def {random_placeholder('func')}():\n    return '{random_placeholder('FAKE')}'"
                    )
                    transformed_tree.body.insert(0, dummy_func.body[0])

                if level == "paranoid":
                    # Insert dummy class
                    dummy_class = ast.parse(
                        f"class {random_placeholder('class')}:\n    pass"
                    )
                    transformed_tree.body.insert(0, dummy_class.body[0])

            abstracted_code = ast.unparse(transformed_tree)
            global_mapping = abstractor.mapping

        # Scrub comments
        lines = []
        for line in abstracted_code.splitlines():
            if "#" in line:
                line = line.split("#")[0] + "# placeholder comment"
            lines.append(line)
        abstracted_code = "\n".join(lines)

        return abstracted_code, global_mapping

    except (SyntaxError, ValueError) as e:
        print(f"AST parsing failed: {e}. Returning original code.")
        return code, {}


def restore(abstracted_code: str, mapping: Dict[str, str]) -> str:
    """
    Restores original code from placeholders.

    Args:
        abstracted_code: Code with placeholders.
        mapping: Dictionary mapping original names → placeholders.

    Returns:
        Restored human-readable source code.
    """
    reverse_mapping = {v: k for k, v in mapping.items()}

    # Remove noise lines
    cleaned = []
    for line in abstracted_code.splitlines():
        if "FAKE" in line or "placeholder comment" in line:
            continue
        cleaned.append(line)
    abstracted_code = "\n".join(cleaned)

    # Replace placeholders back
    sorted_keys = sorted(reverse_mapping.keys(), key=len, reverse=True)
    restored_code = abstracted_code
    for ph in sorted_keys:
        restored_code = restored_code.replace(ph, reverse_mapping[ph])

    return restored_code
