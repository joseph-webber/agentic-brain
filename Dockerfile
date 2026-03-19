FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml pyproject.toml
COPY README.md README.md
COPY src src
COPY examples examples

# Install package with all optional dependencies
RUN pip install --no-cache-dir -e ".[all]"

# Expose API port
EXPOSE 8000

# Create data directory
RUN mkdir -p /app/data

# Default command: run the chat example with memory
# You can override this in docker-compose or docker run
CMD ["python", "-m", "agentic_brain.examples.chat_with_memory"]
