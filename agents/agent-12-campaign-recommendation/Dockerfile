FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-12-campaign-recommendation ./agents/agent-12-campaign-recommendation

ENV PYTHONPATH=/app/packages:/app/agents/agent-12-campaign-recommendation

CMD ["python", "-m", "agent.service"]