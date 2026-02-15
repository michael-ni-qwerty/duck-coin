FROM python:3.12-slim

WORKDIR /app

# System deps for asyncpg, cffi, pynacl + curl for Atlas install
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install Atlas CLI
RUN curl -sSf https://atlasgo.sh | sh

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
