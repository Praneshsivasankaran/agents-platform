FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-09-audience-segmentation ./agents/agent-09-audience-segmentation

ENV PYTHONPATH=/app/packages:/app/agents/agent-09-audience-segmentation

CMD ["python", "-m", "agent.service"]