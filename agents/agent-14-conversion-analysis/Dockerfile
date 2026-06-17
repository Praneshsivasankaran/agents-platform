FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-14-conversion-analysis ./agents/agent-14-conversion-analysis

ENV PYTHONPATH=/app/packages:/app/agents/agent-14-conversion-analysis

CMD ["python", "-m", "agent.service"]