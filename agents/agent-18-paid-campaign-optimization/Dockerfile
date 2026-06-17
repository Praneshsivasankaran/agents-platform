FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-18-paid-campaign-optimization ./agents/agent-18-paid-campaign-optimization

ENV PYTHONPATH=/app/packages:/app/agents/agent-18-paid-campaign-optimization

CMD ["python", "-m", "agent.service"]
