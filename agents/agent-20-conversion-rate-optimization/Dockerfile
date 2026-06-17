FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-20-conversion-rate-optimization ./agents/agent-20-conversion-rate-optimization

ENV PYTHONPATH=/app/packages:/app/agents/agent-20-conversion-rate-optimization

CMD ["python", "-m", "agent.service"]
