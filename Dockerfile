FROM python:3.12-slim

ENV TZ=Europe/Berlin
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Nicht als root laufen. /app/data ist der Mountpoint fuer das persistente
# Volume (SQLite-DB) - der App-User braucht dort Schreibrechte, daher schon
# hier anlegen und chown-en, bevor auf den unprivilegierten User gewechselt
# wird. HOME/XDG_CACHE_HOME zeigen bewusst in dieses Volume, damit der
# mac-vendor-lookup-Cache (~/.cache/mac-vendors.txt) persistiert statt bei
# jedem Container-Rebuild verloren zu gehen (statt des frueheren
# /root/.cache-Workarounds).
RUN useradd -r -u 10001 app && mkdir -p /app/data && chown app /app/data
ENV HOME=/app/data XDG_CACHE_HOME=/app/data/.cache
USER app

EXPOSE 8090

CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8090"]
