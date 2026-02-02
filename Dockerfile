FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only runtime-required files
COPY src/ ./src/
COPY data/Celonis_Garage_Enriched_Data_Final.csv ./data/
COPY data/route_stats.json ./data/
COPY scripts/ ./scripts/

# Expose port
EXPOSE 9001

# Run the application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "9001"]
