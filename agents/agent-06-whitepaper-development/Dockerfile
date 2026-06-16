FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-06-whitepaper-development ./agents/agent-06-whitepaper-development

ENV PYTHONPATH=/app/packages:/app/agents/agent-06-whitepaper-development

CMD ["python", "-m", "agent.service"]
