FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-27-consent-compliance-review ./agents/agent-27-consent-compliance-review

ENV PYTHONPATH=/app/packages:/app/agents/agent-27-consent-compliance-review

CMD ["python", "-m", "agent.service"]
