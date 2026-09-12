FROM python:3.12-slim
WORKDIR /app
COPY harness/pyproject.toml harness/README.md /tmp/harness/
COPY harness/src /tmp/harness/src
RUN pip install --no-cache-dir /tmp/harness
COPY smb-session/pyproject.toml /tmp/smb-session/pyproject.toml
COPY smb-session/src /tmp/smb-session/src
RUN pip install --no-cache-dir /tmp/smb-session
COPY corp-orchestrator/pyproject.toml corp-orchestrator/README.md ./
COPY corp-orchestrator/src ./src
RUN sed -i '/aegis-harness/d' pyproject.toml \
 && sed -i '/aegis-smb-session/d' pyproject.toml \
 && pip install --no-cache-dir .
EXPOSE 8094
RUN useradd -r -u 10001 -m -d /home/aegis aegis
ENV HOME=/home/aegis
USER aegis
CMD ["python", "-m", "aegis_corp_orchestrator.main"]
