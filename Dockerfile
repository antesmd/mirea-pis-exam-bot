FROM python:3.13.14-alpine3.24 AS builder

WORKDIR /app

RUN pip install uv --no-cache-dir

COPY ./pyproject.toml ./uv.lock ./
RUN uv sync --no-dev --frozen --compile-bytecode --no-cache


FROM python:3.13.14-alpine3.24

WORKDIR /app

RUN addgroup -g 1001 -S pis-bot && adduser -S pis-bot -u 1001 -G pis-bot

COPY --chown=pis-bot:pis-bot --from=builder /app/.venv /app/.venv

COPY --chown=pis-bot:pis-bot ./main.py ./main.py
COPY --chown=pis-bot:pis-bot ./questions.json ./questions.json

USER pis-bot

ENV PATH="/app/.venv/bin:${PATH}"
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
