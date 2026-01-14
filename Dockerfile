FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

# Copy necessary files only (not local configs)
COPY server.py .
COPY viral_scout.py .
COPY cookie_utils.py .
COPY scraper.py .
COPY accounts.json .
COPY publisher.py .
COPY config_api.json .
COPY prompts/ prompts/

# Create directories for data persistence
RUN mkdir -p /app/data

# Environment
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run server
CMD ["python", "server.py"]
