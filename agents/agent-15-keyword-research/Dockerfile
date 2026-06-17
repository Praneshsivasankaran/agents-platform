FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-15-keyword-research ./agents/agent-15-keyword-research

ENV PYTHONPATH=/app/packages:/app/agents/agent-15-keyword-research

CMD ["python", "-m", "agent.service"]
