FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TWKS_DATA_DIR=/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

# если в репозиторий залит zip с проектом - разворачиваем его на месте
RUN set -e; \
    for z in /app/*.zip; do \
        if [ -f "$z" ]; then echo "unzip: $z"; unzip -o -q "$z" -d /app; fi; \
    done

RUN req="$(find /app -maxdepth 3 -type f -name requirements.txt | head -n 1)"; \
    echo "requirements: ${req:-NOT FOUND}"; \
    test -n "$req"; \
    pip install --no-cache-dir -r "$req"

EXPOSE 8000

CMD ["sh", "-c", "f=\"$(find /app -maxdepth 4 -type f -name run.py | head -n 1)\"; exec python \"$f\""]
