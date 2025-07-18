# Basis-Image
FROM python:3.11-slim

# Arbeitsverzeichnis
WORKDIR /app

# System-Pakete für OCR und PDF-Verarbeitung installieren
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       tesseract-ocr \
       poppler-utils \
       ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Projektdateien kopieren
COPY . /app

# Python-Abhängigkeiten installieren (inkl. ocrmypdf)
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install notebook

# Standard-Port für Jupyter
EXPOSE 8888

# Startbefehl für Jupyter Notebook (kann in docker-compose überschrieben werden)
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--allow-root", "--NotebookApp.token=", "--NotebookApp.disable_check_xsrf=True"]