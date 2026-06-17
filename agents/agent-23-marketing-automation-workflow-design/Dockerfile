FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-23-marketing-automation-workflow-design ./agents/agent-23-marketing-automation-workflow-design

ENV PYTHONPATH=/app/packages:/app/agents/agent-23-marketing-automation-workflow-design

CMD ["python", "-m", "agent.service"]
