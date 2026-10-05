# Same harness locally, in CI, or as a scheduled job. Replay mode needs no secrets.
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml ./
COPY evalgate ./evalgate
RUN uv pip install --system -e ".[docs,rag,agent]"
COPY projects ./projects
COPY tests ./tests
ENV EVALGATE_MODE=replay
ENTRYPOINT ["evalgate"]
CMD ["run", "telemetry-attribution"]
