"""Render Workflows entry point.

Collects all workflow apps and starts the SDK worker. Run with:

    python -m workflows.main

To add a new workflow domain, create a new subdirectory under ``workflows/``
with its own ``tasks.py`` and ``Workflows()`` app, then import it here.
"""

from render_sdk import Workflows

from workflows.research import app as research_app

app = Workflows.from_workflows(research_app)

if __name__ == "__main__":
    app.start()
