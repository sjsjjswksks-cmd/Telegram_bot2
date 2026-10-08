FROM python:3.12-slim
WORKDIR /app
COPY . .
ENV PORT=8080 DATA_DIR=/app/data
EXPOSE 8080
CMD ["python3","app.py"]
