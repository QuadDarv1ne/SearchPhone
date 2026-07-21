FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p reports cache logs

# Run as non-root user
RUN useradd -m -u 1000 searchphone && chown -R searchphone:searchphone /app
USER searchphone

ENTRYPOINT ["python", "search_phone.py"]