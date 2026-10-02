FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

# Pre-create the uploads dir so that when the kyc_uploads named volume is first
# mounted here, Docker initializes it owned by appuser (not root) and the
# non-root process can write seeded + uploaded files.
RUN mkdir -p /app/app/uploads

RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["./entrypoint.sh"]
