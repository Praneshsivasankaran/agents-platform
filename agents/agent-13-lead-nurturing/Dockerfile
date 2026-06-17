FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-13-lead-nurturing ./agents/agent-13-lead-nurturing

ENV PYTHONPATH=/app/packages:/app/agents/agent-13-lead-nurturing

CMD ["python", "-m", "agent.service"]