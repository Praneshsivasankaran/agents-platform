FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-21-performance-reporting ./agents/agent-21-performance-reporting

ENV PYTHONPATH=/app/packages:/app/agents/agent-21-performance-reporting

CMD ["python", "-m", "agent.service"]
