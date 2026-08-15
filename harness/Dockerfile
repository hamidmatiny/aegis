FROM python:3.12-slim
WORKDIR /app
COPY harness/pyproject.toml harness/README.md ./
COPY harness/src ./src
RUN pip install --no-cache-dir .
# Not a long-running server -- run_agent() completes and exits, so there's
# no port to expose here (contrast sdk/python's Dockerfile, which runs a
# persistent reverse-proxy). Point AEGIS_MODEL_ROUTER_URL/AEGIS_AGENT_GATE_URL/
# AEGIS_INTERNAL_TOKEN/AEGIS_AGENT_GATE_API_KEYS at a running stack and pass
# the task as the container command, e.g.:
#   docker run --rm --network aegis_default -e AEGIS_MODEL_ROUTER_URL=http://model-router:8082 ... aegis-harness "search the docs"
ENTRYPOINT ["aegis-harness"]
