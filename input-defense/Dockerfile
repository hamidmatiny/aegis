FROM python:3.12-slim
WORKDIR /app
COPY input-defense/pyproject.toml ./
COPY input-defense/src ./src
RUN pip install --no-cache-dir .
EXPOSE 8090
CMD ["python", "-m", "aegis_input_defense.main"]
