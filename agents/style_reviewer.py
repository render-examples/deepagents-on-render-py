"""
Style reviewer agent — checks naming conventions, code structure,
and readability. Does not flag formatting issues (that's a linter's job).
"""

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agents.tools.git import parse_diff, list_changed_files, get_file_diff
from agents.tools.code_analysis import detect_language, extract_functions


SYSTEM_PROMPT = """\
You are a code style reviewer focused on readability and
maintainability. Given a PR diff:

1. List the changed files to understand scope.
2. For each file with code changes, detect its language and
   extract the diff to review.
3. Extract function signatures to check naming and structure.
4. Focus on: naming clarity, function length, dead code,
   overly complex logic, missing docstrings on public APIs.

Do NOT flag formatting issues (whitespace, indentation, line
length) — those belong to a linter. Focus on human-readable
code quality.
"""


def create_style_reviewer():
    """Return a compiled style reviewer agent graph."""
    llm = ChatOpenAI(model="gpt-4o")
    return create_react_agent(
        model=llm,
        tools=[
            parse_diff,
            list_changed_files,
            get_file_diff,
            detect_language,
            extract_functions,
        ],
        prompt=SYSTEM_PROMPT,
    )
