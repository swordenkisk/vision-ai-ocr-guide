FROM python:3.11-slim

LABEL maintainer="vision-ai-ocr-guide"
LABEL description="Google Cloud Vision AI OCR microservice"
LABEL version="1.0.0"

WORKDIR /app

# Install system dependencies required for image processing libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application source code
COPY src/ ./src/

# Create mount points for input/output volumes
RUN mkdir -p /input /output

VOLUME ["/input", "/output"]

# Default environment (override at runtime)
ENV PYTHONUNBUFFERED=1
ENV MAX_WORKERS=10
ENV LANGUAGE_HINT=en

ENTRYPOINT ["python", "src/batch_processor.py"]
CMD ["/input", "/output"]
