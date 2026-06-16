FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PYTHONPATH=/app/packages:/app/agents/agent-05-editorial-planning

CMD ["python", "-c", "import core, agent.graph; print('agent-05-editorial-planning image ready')"]

