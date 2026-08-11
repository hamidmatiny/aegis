FROM python:3.12-slim
WORKDIR /app
COPY redteam/pyproject.toml redteam/README.md ./
COPY redteam/src ./src
RUN pip install --no-cache-dir .
EXPOSE 8092
RUN useradd -r -u 10001 -m -d /home/aegis aegis
ENV HOME=/home/aegis
USER aegis

CMD ["python", "-m", "aegis_redteam.main"]
