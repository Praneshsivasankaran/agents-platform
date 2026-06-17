FROM python:3.11-slim

WORKDIR /app

COPY packages ./packages
COPY agents/agent-17-landing-page-optimization ./agents/agent-17-landing-page-optimization

ENV PYTHONPATH=/app/packages:/app/agents/agent-17-landing-page-optimization

CMD ["python", "-m", "agent.service"]
