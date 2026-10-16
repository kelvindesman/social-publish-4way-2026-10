# Arms 1 + 2a + proxy: stdlib Python only.
FROM python:3.12-slim
LABEL ld-poc=1
RUN apt-get update && apt-get install -y --no-install-recommends librsvg2-bin fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY common /app/common
COPY arms /app/arms
COPY proxy /app/proxy
COPY render.py /app/render.py
