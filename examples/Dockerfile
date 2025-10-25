FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastdjango[postgres] uvicorn

# Copy application
COPY minimal_postgres.py /app/main.py

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "main.py"]