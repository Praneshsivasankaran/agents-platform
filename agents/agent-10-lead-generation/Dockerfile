FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-10-lead-generation ./agents/agent-10-lead-generation

ENV PYTHONPATH=/app/packages:/app/agents/agent-10-lead-generation

CMD ["python", "-m", "agent.service"]