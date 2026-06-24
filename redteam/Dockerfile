FROM python:3.12-slim
WORKDIR /app
COPY redteam/pyproject.toml redteam/README.md ./
COPY redteam/src ./src
RUN pip install --no-cache-dir .
EXPOSE 8092
CMD ["python", "-m", "aegis_redteam.main"]
