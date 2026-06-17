FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-11-lead-scoring ./agents/agent-11-lead-scoring

ENV PYTHONPATH=/app/packages:/app/agents/agent-11-lead-scoring

CMD ["python", "-m", "agent.service"]