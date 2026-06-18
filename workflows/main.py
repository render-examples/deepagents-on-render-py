"""Render Workflows entry point.

Collects all workflow apps and starts the SDK.
To add a new workflow domain, create a new subdirectory under workflows/
with its own tasks.py and Workflows() app, then import it here.
"""

from render_sdk import Workflows

from workflows.code_review import app as code_review_app

app = Workflows.from_workflows(code_review_app)

if __name__ == "__main__":
    app.start()
