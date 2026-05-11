FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

# Copy directories and entry points
COPY core/ core/
COPY config/__init__.py config/__init__.py
COPY config/cookie_utils.py config/cookie_utils.py
COPY data/__init__.py data/__init__.py
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
