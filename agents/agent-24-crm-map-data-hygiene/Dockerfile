FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-24-crm-map-data-hygiene ./agents/agent-24-crm-map-data-hygiene

ENV PYTHONPATH=/app/packages:/app/agents/agent-24-crm-map-data-hygiene

CMD ["python", "-m", "agent.service"]
