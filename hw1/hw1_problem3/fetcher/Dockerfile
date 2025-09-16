FROM python:3.11-slim
WORKDIR /app
COPY fetch.py /app/
RUN mkdir -p /shared/input /shared/analysis /shared/status
CMD ["python", "-u", "/app/fetch.py"]