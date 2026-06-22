FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Default to the web service. The Workflows worker is started separately with
# `python -m workflows.main` (on Render, that's the Workflow service).
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
