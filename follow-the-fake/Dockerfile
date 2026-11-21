FROM python:3.12-slim

# Tesseract OCR z językiem polskim + biblioteki dla OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-pol tesseract-ocr-eng libglib2.0-0 libgl1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# opcjonalne modele twarzy – nie przerywaj budowania, gdy brak sieci
RUN python tools/download_models.py || true
RUN python tools/make_demo.py

ENV PORT=8000 HOST=0.0.0.0 FTF_DB=/app/data/db/ftf.sqlite
EXPOSE 8000
CMD ["python", "app.py"]
