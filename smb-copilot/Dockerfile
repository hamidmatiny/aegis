FROM python:3.12-slim
WORKDIR /app
COPY smb-copilot/pyproject.toml smb-copilot/README.md ./
COPY smb-copilot/src ./src
RUN pip install --no-cache-dir .
EXPOSE 8093
RUN useradd -r -u 10001 -m -d /home/aegis aegis
ENV HOME=/home/aegis
USER aegis

CMD ["python", "-m", "aegis_smb_copilot.main"]
