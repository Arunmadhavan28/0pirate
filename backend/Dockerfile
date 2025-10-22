FROM python:3.11-slim

WORKDIR /app

# Install dependencies directly
COPY requirements.txt .
RUN pip install -r requirements.txt

# Debug - check what's installed
RUN pip list | grep -E "(uvicorn|razorpay|fastapi)" || echo "Some packages missing"
RUN python -c "import uvicorn; print('uvicorn OK')" || echo "uvicorn failed"
RUN python -c "import razorpay; print('razorpay OK')" || echo "razorpay failed"

COPY seccomp_profile.json /app/seccomp_profile.json

# Copy app
COPY . .

# Simple command
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
