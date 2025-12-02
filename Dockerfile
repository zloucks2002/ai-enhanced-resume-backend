FROM python:3.11-slim

WORKDIR /app

# System deps for Playwright + pandoc
RUN apt-get update && apt-get install -y \
    curl wget \
    libglib2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    libasound2 \
    libjpeg62-turbo \
    libxshmfence1 \
    libxkbcommon0 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    pandoc \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser
RUN python -m playwright install --with-deps chromium

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
