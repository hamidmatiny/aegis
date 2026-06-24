FROM python:3.12-slim
WORKDIR /app
COPY output-defense/pyproject.toml output-defense/README.md ./
COPY output-defense/src ./src
RUN pip install --no-cache-dir .
EXPOSE 8091
CMD ["python", "-m", "aegis_output_defense.main"]
