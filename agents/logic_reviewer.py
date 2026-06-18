"""
Logic reviewer agent — catches bugs, off-by-one errors, missing
edge cases, and incorrect control flow in a PR diff.
"""

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agents.tools.git import parse_diff, list_changed_files, get_file_diff
from agents.tools.code_analysis import detect_language, extract_functions


SYSTEM_PROMPT = """\
You are a logic-focused code reviewer. Given a PR diff:

1. List the changed files to understand scope.
2. For each file with code changes, extract the diff and
   analyze the logic carefully.
3. Extract function signatures to understand boundaries.
4. Focus on: off-by-one errors, null/None handling, missing
   error cases, incorrect boolean logic, race conditions,
   resource leaks, and boundary conditions.

Be precise. Cite specific line numbers and explain what could
go wrong. If the logic is correct, say so.
"""


def create_logic_reviewer():
    """Return a compiled logic reviewer agent graph."""
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
