# Basis-Image
FROM python:3.11-slim

# Systempakete installieren (für pdfkit)
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    curl \
    build-essential \
    && apt-get clean

# Arbeitsverzeichnis
WORKDIR /app

# Projektdateien kopieren
COPY . /app

# Abhängigkeiten installieren
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install notebook

# Standard-Port für Jupyter
EXPOSE 8888

# Startbefehl für Jupyter Notebook
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--NotebookApp.token=''"]