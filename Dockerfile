FROM python:3.12-slim

ENV TZ=Europe/Berlin
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# mac-vendor-lookup schreibt seinen Cache nach ~/.cache/mac-vendors.txt und
# legt das Verzeichnis dabei nicht zuverlaessig selbst an (FileNotFoundError
# im leeren Container-Image) - daher hier vorab anlegen.
RUN mkdir -p /root/.cache

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
