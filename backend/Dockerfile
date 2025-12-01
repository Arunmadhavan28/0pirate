FROM python:3.11-slim-bookworm

WORKDIR /app

# 1. Install System Deps AND Docker Client/Daemon
# 'docker.io' provides the daemon and client on Debian Bookworm
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc build-essential \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --default-timeout=1000 \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    pytest \
    -r requirements.txt

# 3. Copy Code & Entrypoint
COPY . .
COPY entrypoint.sh /entrypoint.sh

# 4. Make script executable
RUN chmod +x /entrypoint.sh

EXPOSE 8080

# 5. Set the Entrypoint
ENTRYPOINT ["/entrypoint.sh"]