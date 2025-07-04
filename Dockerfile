# Usa Python 3.11.8 oficial
FROM python:3.11.8-slim

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Copia todo al contenedor
COPY . /app

# Actualiza pip e instala dependencias
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expone el puerto 10000 (cámbialo si tu app usa otro)
EXPOSE 10000

# Comando para arrancar tu app con Gunicorn
CMD ["gunicorn", "main:app"]