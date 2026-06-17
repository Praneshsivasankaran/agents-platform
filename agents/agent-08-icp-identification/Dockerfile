FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-08-icp-identification ./agents/agent-08-icp-identification

ENV PYTHONPATH=/app/packages:/app/agents/agent-08-icp-identification

CMD ["python", "-m", "agent.service"]

