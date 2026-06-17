FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-19-multi-channel-campaign-planning ./agents/agent-19-multi-channel-campaign-planning

ENV PYTHONPATH=/app/packages:/app/agents/agent-19-multi-channel-campaign-planning

CMD ["python", "-m", "agent.service"]
