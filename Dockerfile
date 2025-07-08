FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libxml2-dev libxslt1-dev git && \
    rm -rf /var/lib/apt/lists/*

# Install required Python packages
RUN pip install --no-cache-dir paho-mqtt==1.6.1 xmltodict

# Copy source code
COPY . /app

# Run the script
CMD ["python", "owl.py"]

