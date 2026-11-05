FROM python:3.14-slim AS builder
ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
RUN pip install --no-cache-dir uv==0.13.6
WORKDIR /build
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# Para Docker Compose.
FROM python:3.14-slim AS runtime
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=builder /opt/venv /opt/venv
WORKDIR /srv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Tareas en Lambda sin HTTP: por ahora, las migraciones del deploy.
FROM runtime AS lambda-task
CMD ["python", "-m", "awslambdaric", "app.migrate.handler"]

# La API en Lambda: el adaptador traduce los eventos a HTTP, sin cambiar FastAPI.
FROM runtime AS lambda-api
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.0.0 /lambda-adapter /opt/extensions/lambda-adapter
ENV AWS_LWA_PORT=8000 AWS_LWA_READINESS_CHECK_PATH=/health
