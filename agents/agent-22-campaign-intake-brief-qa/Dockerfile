FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-22-campaign-intake-brief-qa ./agents/agent-22-campaign-intake-brief-qa

ENV PYTHONPATH=/app/packages:/app/agents/agent-22-campaign-intake-brief-qa

CMD ["python", "-m", "agent.service"]
