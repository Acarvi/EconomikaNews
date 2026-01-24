FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

# Copy directories and entry points
COPY core/ core/
COPY config/ config/
COPY data/ data/
COPY prompts/ prompts/
COPY server.py .
COPY requirements.txt .
COPY utils/ utils/

# Create directories for data persistence
RUN mkdir -p /app/data

# Environment
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run server
CMD ["python", "server.py"]
