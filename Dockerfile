FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy environment code
COPY email_triage_env/ ./email_triage_env/
COPY openenv.yaml .

# Health check - simple endpoint verification
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from email_triage_env.env import EmailTriageEnv; EmailTriageEnv()" || exit 1

# Start server
CMD ["python", "-m", "uvicorn", "email_triage_env.app:app", "--host", "0.0.0.0", "--port", "8000"]
