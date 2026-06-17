FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-28-campaign-launch-readiness-qa ./agents/agent-28-campaign-launch-readiness-qa

ENV PYTHONPATH=/app/packages:/app/agents/agent-28-campaign-launch-readiness-qa

CMD ["python", "-m", "agent.service"]
