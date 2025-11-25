FROM python:3.12.8-slim

WORKDIR /usr/src/higgsfield-api

ENV PYTHONPATH=/usr/src/higgsfield-api:/usr/src/higgsfield-api/src

COPY requirements/base.txt /requirements/

RUN apt-get update && \
    apt update && \
    apt install -y curl && \
    pip install --upgrade pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r /requirements/base.txt && \
    rm -rf /root/.cache/pip

