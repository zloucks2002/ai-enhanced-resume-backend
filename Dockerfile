FROM python:3.11-slim

# Install WeasyPrint dependencies (Debian Bookworm versions)
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libcairo2 \
    libcairo-gobject2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    curl \
    pandoc \
    && apt-get clean

# Set workdir
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Expose port
EXPOSE 8000

# Run API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
