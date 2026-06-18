"""
Security reviewer agent — scans a PR diff for vulnerabilities,
credential leaks, unsafe patterns, and suspicious dependencies.
"""

from langgraph.prebuilt import create_react_agent

from agents.llm import get_llm

from agents.tools.git import parse_diff, list_changed_files, get_file_diff
from agents.tools.code_analysis import detect_language, find_patterns, check_imports


SYSTEM_PROMPT = """\
You are a security-focused code reviewer. Given a PR diff:

1. List the changed files to understand scope.
2. For each file with code changes, detect its language,
   extract the diff, and run find_patterns to scan for risks.
3. Check imports for known-vulnerable or suspicious packages.
4. Report each finding with severity (critical/high/medium/low),
   the file path, line number, and a clear explanation.

If you find no issues, say so explicitly. Do not invent problems.
"""


def create_security_reviewer():
    """Return a compiled security reviewer agent graph."""
    llm = get_llm()
    return create_react_agent(
        model=llm,
        tools=[
            parse_diff,
            list_changed_files,
            get_file_diff,
            detect_language,
            find_patterns,
            check_imports,
        ],
        prompt=SYSTEM_PROMPT,
    )
