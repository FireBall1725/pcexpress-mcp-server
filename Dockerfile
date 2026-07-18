# PC Express MCP server. The image serves MCP over HTTP/SSE (for Home Assistant / k8s):
#   /sse       - the MCP SSE endpoint (posts go to /messages/)
#   /health    - unauthenticated health check for probes
# For a local stdio server (Claude Desktop), run pcexpress_mcp_server.py directly instead.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./

# Rotating refresh token + cached access token live here; mount a volume in prod.
ENV PCEXPRESS_STATE_DIR=/data \
    PCEXPRESS_HTTP=1 \
    PCEXPRESS_HTTP_PORT=8090
VOLUME ["/data"]
EXPOSE 8090

ENTRYPOINT ["python", "pcexpress_mcp_server.py", "--http"]
