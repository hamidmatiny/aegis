FROM python:3.12-slim
WORKDIR /app
COPY smb-session/pyproject.toml /tmp/smb-session/pyproject.toml
COPY smb-session/src /tmp/smb-session/src
RUN pip install --no-cache-dir /tmp/smb-session
COPY smb-copilot/pyproject.toml smb-copilot/README.md ./
COPY smb-copilot/src ./src
RUN sed -i '/aegis-smb-session/d' pyproject.toml && pip install --no-cache-dir .
EXPOSE 8093
RUN useradd -r -u 10001 -m -d /home/aegis aegis
ENV HOME=/home/aegis
USER aegis

CMD ["python", "-m", "aegis_smb_copilot.main"]
