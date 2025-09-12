FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome using a different approach - use Chromium instead
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install boto3 for S3
RUN pip install boto3

# Copy application code
COPY . .

# Set environment
ENV PYTHONPATH=/app
ENV DISPLAY=:99

# Run cookie refresh
CMD ["python3", "refresh_cookies.py"]