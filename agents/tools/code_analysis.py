"""Tools for lightweight static analysis of code snippets."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from langchain.tools import tool

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".swift": "swift",
    ".php": "php",
    ".sh": "shell",
    ".bash": "shell",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".md": "markdown",
    ".dockerfile": "dockerfile",
}

_FUNCTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "python": re.compile(
        r"^[ \t]*(async\s+)?def\s+(\w+)\s*\(", re.MULTILINE
    ),
    "javascript": re.compile(
        r"(?:^|\s)(?:async\s+)?function\s+(\w+)\s*\(|"
        r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?",
        re.MULTILINE,
    ),
    "typescript": re.compile(
        r"(?:^|\s)(?:async\s+)?function\s+(\w+)\s*\(|"
        r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?|"
        r"(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{",
        re.MULTILINE,
    ),
    "go": re.compile(r"^func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(", re.MULTILINE),
    "rust": re.compile(
        r"^[ \t]*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", re.MULTILINE
    ),
    "java": re.compile(
        r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(",
        re.MULTILINE,
    ),
    "ruby": re.compile(r"^\s*def\s+(\w+)", re.MULTILINE),
}

DANGEROUS_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "python": [
        (r"\beval\s*\(", "eval() call — potential code injection"),
        (r"\bexec\s*\(", "exec() call — potential code injection"),
        (r"\bos\.system\s*\(", "os.system() — use subprocess instead"),
        (r"\bpickle\.loads?\s*\(", "pickle deserialization — unsafe with untrusted data"),
        (r"__import__\s*\(", "dynamic import — potential code injection"),
        (r"subprocess\..*shell\s*=\s*True", "shell=True in subprocess — injection risk"),
    ],
    "javascript": [
        (r"\beval\s*\(", "eval() call — potential code injection"),
        (r"innerHTML\s*=", "innerHTML assignment — potential XSS"),
        (r"document\.write\s*\(", "document.write() — potential XSS"),
        (r"new\s+Function\s*\(", "new Function() — potential code injection"),
    ],
    "typescript": [
        (r"\beval\s*\(", "eval() call — potential code injection"),
        (r"innerHTML\s*=", "innerHTML assignment — potential XSS"),
        (r"\bany\b", "usage of 'any' type — bypasses type safety"),
    ],
    "_common": [
        (r"(?i)password\s*=\s*['\"][^'\"]+['\"]", "possible hardcoded password"),
        (r"(?i)api_?key\s*=\s*['\"][^'\"]+['\"]", "possible hardcoded API key"),
        (r"(?i)secret\s*=\s*['\"][^'\"]+['\"]", "possible hardcoded secret"),
        (r"(?i)token\s*=\s*['\"][^'\"]+['\"]", "possible hardcoded token"),
    ],
}


@tool
def detect_language(file_path: str) -> str:
    """Detect the programming language of a file from its extension.

    Returns the language name (e.g. 'python', 'typescript', 'go')
    or 'unknown' if the extension is not recognized.
    """
    suffix = PurePosixPath(file_path).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(suffix, "unknown")


@tool
def extract_functions(code: str, language: str) -> list[dict]:
    """Extract function and method signatures from a code snippet.

    Returns a list of objects with the function name and the line number
    where it is defined. Supports python, javascript, typescript, go,
    rust, java, and ruby.
    """
    pattern = _FUNCTION_PATTERNS.get(language)
    if pattern is None:
        return []

    results: list[dict] = []
    for match in pattern.finditer(code):
        name = next((g for g in match.groups() if g is not None), None)
        if name is None:
            continue
        line_number = code[: match.start()].count("\n") + 1
        results.append({"name": name, "line": line_number})

    return results


@tool
def find_patterns(code: str, file_path: str) -> list[dict]:
    """Scan code for dangerous or suspicious patterns.

    Checks for language-specific risks (eval, exec, injection vectors)
    and common credential leaks (hardcoded passwords, API keys, secrets).
    Returns a list of findings with the matched line, line number,
    and a description of the concern.
    """
    suffix = PurePosixPath(file_path).suffix.lower()
    language = EXTENSION_TO_LANGUAGE.get(suffix, "unknown")

    patterns = DANGEROUS_PATTERNS.get("_common", [])[:]
    patterns.extend(DANGEROUS_PATTERNS.get(language, []))

    findings: list[dict] = []
    lines = code.splitlines()
    for i, line in enumerate(lines, start=1):
        for regex, description in patterns:
            if re.search(regex, line):
                findings.append({
                    "line_number": i,
                    "line": line.strip(),
                    "concern": description,
                })

    return findings


@tool
def check_imports(code: str, language: str) -> list[dict]:
    """Extract import statements from code.

    Returns a list of imported module/package names with their line numbers.
    Supports python, javascript, and typescript.
    """
    results: list[dict] = []
    lines = code.splitlines()

    if language == "python":
        import_re = re.compile(
            r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w., ]+))"
        )
        for i, line in enumerate(lines, start=1):
            m = import_re.match(line)
            if m:
                module = m.group(1) or m.group(2)
                for mod in module.split(","):
                    results.append({
                        "module": mod.strip(),
                        "line": i,
                    })

    elif language in ("javascript", "typescript"):
        import_re = re.compile(
            r"""^\s*import\s+(?:.*\s+from\s+)?['"]([^'"]+)['"]"""
        )
        require_re = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""")
        for i, line in enumerate(lines, start=1):
            for pattern in (import_re, require_re):
                m = pattern.search(line)
                if m:
                    results.append({"module": m.group(1), "line": i})

    return results
