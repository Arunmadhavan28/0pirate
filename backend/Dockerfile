FROM python:3.11 AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN python -m venv .venv
COPY requirements.txt ./
RUN .venv/bin/pip install -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app/.venv .venv/
COPY . .

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
