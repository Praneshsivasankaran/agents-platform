FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-25-utm-tracking-governance ./agents/agent-25-utm-tracking-governance

ENV PYTHONPATH=/app/packages:/app/agents/agent-25-utm-tracking-governance

CMD ["python", "-m", "agent.service"]
