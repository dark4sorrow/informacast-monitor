# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install troubleshooting tools
RUN apt-get update && apt-get install -y curl dnsutils && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose internal port
EXPOSE 5082

# Run with Gunicorn
# --timeout 90 handles slower API handshakes
# --workers 3 allows concurrent dashboard data loading
CMD ["gunicorn", "--workers", "3", "--timeout", "90", "-b", "0.0.0.0:5082", "app:app"]