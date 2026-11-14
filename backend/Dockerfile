FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Install uv from official binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install dependencies
COPY pyproject.toml uv.lock* ./
RUN uv pip install --system -r pyproject.toml

# Copy application source
COPY . .

VOLUME ["/data"]
ENV DB_PATH=/data/astrovitals.db
ENV APP_ENV=prod
ENV HTTP_HOST=0.0.0.0
ENV HTTP_PORT=8998

EXPOSE 8998
USER nobody

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8998", "--workers", "1", "--no-access-log"]
