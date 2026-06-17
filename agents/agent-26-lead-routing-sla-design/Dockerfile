FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-26-lead-routing-sla-design ./agents/agent-26-lead-routing-sla-design

ENV PYTHONPATH=/app/packages:/app/agents/agent-26-lead-routing-sla-design

CMD ["python", "-m", "agent.service"]
