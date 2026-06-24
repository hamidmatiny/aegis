FROM python:3.12-slim
WORKDIR /app
COPY sdk/python/pyproject.toml sdk/python/README.md ./
COPY sdk/python/src ./src
RUN pip install --no-cache-dir .
EXPOSE 8080
ENV AEGIS_SDK_PROXY_PORT=8080
CMD ["aegis-sdk-proxy"]
