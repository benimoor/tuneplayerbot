FROM python:3.12-slim
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "app.main", "bot"]
