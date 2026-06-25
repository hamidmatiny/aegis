FROM python:3.12-slim
WORKDIR /app
ARG INSTALL_ML=false
COPY input-defense/pyproject.toml input-defense/README.md ./
COPY input-defense/src ./src
RUN if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir '.[ml]'; else pip install --no-cache-dir .; fi
EXPOSE 8090
CMD ["python", "-m", "aegis_input_defense.main"]
