FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-16-ad-copy-creation ./agents/agent-16-ad-copy-creation

ENV PYTHONPATH=/app/packages:/app/agents/agent-16-ad-copy-creation

CMD ["python", "-m", "agent.service"]
