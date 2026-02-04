# Use official Python image
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python script
COPY otel_span_log.py ./

# Run the script
CMD ["python", "otel_span_log.py"]

