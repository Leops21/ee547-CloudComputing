FROM python:3.11-slim
WORKDIR /app
COPY fetch_and_process.py .
RUN mkdir -p /data/input /data/output
ENTRYPOINT ["python", "fetch_and_process.py"]
CMD ["/data/input/urls.txt", "/data/output"]
