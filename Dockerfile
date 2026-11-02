FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY frontend frontend
RUN useradd -r -u 10001 app && mkdir -p /data && chown app /data
USER app
# SQLite lives on a mounted volume; set DATABASE_URL to Postgres instead if you prefer.
ENV DATABASE_URL=sqlite:////data/lab.db
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:%s/health'%os.getenv('PORT','8000'))"
# ONE worker on purpose: the job runner is in-process (see README: Scaling).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers"]
