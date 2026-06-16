FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-07-case-study-generation ./agents/agent-07-case-study-generation

ENV PYTHONPATH=/app/packages:/app/agents/agent-07-case-study-generation

CMD ["python", "-m", "agent.service"]
