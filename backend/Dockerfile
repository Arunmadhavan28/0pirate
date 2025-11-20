# Use the full image instead of slim to ensure robust SSL/Build libraries
FROM python:3.11

WORKDIR /app

# Upgrade pip to the latest version immediately
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements
COPY requirements.txt .

# Install heavy dependencies individually first to prevent timeout/SSL choke
# This isolates the failure if it happens again
RUN pip install --no-cache-dir numpy pandas
RUN pip install --no-cache-dir langchain

# Install the rest of the dependencies
# Increased timeout and trusted-host flags bypass some SSL inspection issues
RUN pip install --no-cache-dir \
    --default-timeout=1000 \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    pytest \
    -r requirements.txt

# Copy the rest of your backend
COPY . .

# Expose API port
EXPOSE 8080

# Start FastAPI app
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]