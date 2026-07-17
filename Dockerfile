# PC Express MCP server (stdio). For a network endpoint (Home Assistant / k8s),
# wrap this with a stdio->SSE bridge such as supergateway — see DEPLOYMENT.md.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./

# Rotating refresh token + cached access token live here; mount a volume in prod.
ENV PCEXPRESS_STATE_DIR=/data
VOLUME ["/data"]

ENTRYPOINT ["python", "pcexpress_mcp_server.py"]
