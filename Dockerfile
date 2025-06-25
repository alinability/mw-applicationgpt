# Basis-Image
FROM python:3.11-slim

# Systempakete installieren (für pdfkit)
RUN apt-get update && apt-get install -y --fix-missing \
    wkhtmltopdf \
    curl \
    build-essential \
    && apt-get clean

# Arbeitsverzeichnis
WORKDIR /app

# Projektdateien kopieren
COPY . /app

# Python-Abhängigkeiten installieren
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install notebook

# Standard-Port für Jupyter
EXPOSE 8888

# Startbefehl für Jupyter Notebook (optional durch CMD in docker-compose überschreibbar)
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--allow-root", "--NotebookApp.token=", "--NotebookApp.disable_check_xsrf=True"]