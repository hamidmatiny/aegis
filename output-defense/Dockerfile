FROM python:3.12-slim
WORKDIR /app
ARG INSTALL_ML=false
COPY output-defense/pyproject.toml output-defense/README.md ./
COPY output-defense/src ./src
RUN if [ "$INSTALL_ML" = "true" ]; then \
      pip install --no-cache-dir '.[ml]' && python -m spacy download en_core_web_sm; \
    else \
      pip install --no-cache-dir .; \
    fi
EXPOSE 8091
CMD ["python", "-m", "aegis_output_defense.main"]
