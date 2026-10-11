"""
Patch generation, scope validation, and application module for CodeGuard AI.
Guarantees patch path safety, bounds scope, and generates unified diffs.
"""

from typing import Tuple, Optional, List
from pathlib import Path
import difflib
import uuid
import re
from codeguard.models import Finding, PatchProposal, FindingStatus


def validate_patch_scope(
    target_file: str,
    approved_file: str,
    workspace_root: str
) -> Tuple[bool, str]:
    """
    Validate that the patch targets only the intended approved file,
    and that no path traversal or out-of-scope files are affected.
    """
    root = Path(workspace_root).resolve()
    
    # Check for path traversal components
    if ".." in Path(target_file).parts:
        return False, f"Scope violation: Path traversal detected in {target_file}"

    resolved_target = (root / target_file).resolve()
    resolved_approved = (root / approved_file).resolve()

    try:
        resolved_target.relative_to(root)
    except ValueError:
        return False, f"Scope violation: Target file {target_file} is outside workspace root"

    if resolved_target != resolved_approved:
        return False, f"Scope violation: Patch targets {target_file} but approved file was {approved_file}"

    return True, "Scope valid"


def generate_diff(original_text: str, modified_text: str, filename: str) -> str:
    """Generate standard unified diff string between original and modified text."""
    orig_lines = original_text.splitlines(keepends=True)
    mod_lines = modified_text.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm=""
    )
    return "".join(diff)


def apply_patch_string(original_content: str, original_snippet: str, replacement_snippet: str) -> Tuple[bool, str]:
    """
    Replace vulnerable snippet in original content with replacement snippet.
    Returns (success, new_content).
    """
    if original_snippet in original_content:
        new_content = original_content.replace(original_snippet, replacement_snippet, 1)
        return True, new_content

    # If exact match fails, try whitespace-normalized match
    orig_lines = [line.strip() for line in original_snippet.strip().splitlines()]
    file_lines = original_content.splitlines()

    for i in range(len(file_lines) - len(orig_lines) + 1):
        window = [file_lines[i + j].strip() for j in range(len(orig_lines))]
        if window == orig_lines:
            # Found line match; perform replacement preserving leading indentation
            leading_indent = len(file_lines[i]) - len(file_lines[i].lstrip())
            indent_str = file_lines[i][:leading_indent]
            
            replacement_lines = replacement_snippet.splitlines()
            indented_repl = "\n".join(
                indent_str + r.strip() if not r.startswith(indent_str) else r
                for r in replacement_lines
            )

            new_lines = file_lines[:i] + [indented_repl] + file_lines[i + len(orig_lines):]
            return True, "\n".join(new_lines)

    return False, original_content
