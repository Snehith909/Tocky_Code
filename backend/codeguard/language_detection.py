"""
Workspace and language detection for CodeGuard AI.
Inspects file extensions, manifest files, and project structures
to construct language profiles and select applicable scanners.
"""

import os
from typing import List, Dict, Set, Optional
from pathlib import Path
from codeguard.models import LanguageProfile


MANIFEST_MAP = {
    "package.json": ["javascript", "typescript"],
    "tsconfig.json": ["typescript"],
    "pyproject.toml": ["python"],
    "requirements.txt": ["python"],
    "setup.py": ["python"],
    "Pipfile": ["python"],
    "pom.xml": ["java"],
    "build.gradle": ["java"],
    "go.mod": ["go"],
    "Cargo.toml": ["rust"],
    "composer.json": ["php"],
    "Gemfile": ["ruby"],
    "CMakeLists.txt": ["c", "cpp"],
}

EXTENSION_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
}


def detect_languages(target_path: str) -> LanguageProfile:
    """
    Detect languages and manifests in a target path (file or workspace directory).
    """
    path = Path(target_path)
    detected_langs: Set[str] = set()
    found_manifests: List[str] = []

    if path.is_file():
        ext = path.suffix.lower()
        if ext in EXTENSION_MAP:
            detected_langs.add(EXTENSION_MAP[ext])
        return LanguageProfile(
            detected_languages=sorted(list(detected_langs)) if detected_langs else ["generic"],
            manifest_files=[],
            primary_language=list(detected_langs)[0] if detected_langs else "generic"
        )

    # Workspace directory scan
    skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "out", "dist", ".codeguard"}
    
    # Check top-level and 2 levels deep for manifests
    for manifest_name, langs in MANIFEST_MAP.items():
        if (path / manifest_name).exists():
            found_manifests.append(manifest_name)
            detected_langs.update(langs)

    # Scan extensions across directory (sampling up to 1000 files for performance)
    file_count = 0
    lang_frequency: Dict[str, int] = {}

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            file_count += 1
            if file_count > 1000:
                break
            ext = Path(f).suffix.lower()
            if ext in EXTENSION_MAP:
                lang = EXTENSION_MAP[ext]
                detected_langs.add(lang)
                lang_frequency[lang] = lang_frequency.get(lang, 0) + 1
        if file_count > 1000:
            break

    primary = None
    if lang_frequency:
        primary = max(lang_frequency, key=lang_frequency.get)
    elif detected_langs:
        primary = sorted(list(detected_langs))[0]

    return LanguageProfile(
        detected_languages=sorted(list(detected_langs)) if detected_langs else ["generic"],
        manifest_files=found_manifests,
        primary_language=primary
    )
