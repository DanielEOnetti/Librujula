# ==============================
# STAGE 1: Build y dependencias
# ==============================
FROM python:3.11 AS builder

# Establece el directorio de trabajo
WORKDIR /app

# Instala las dependencias del sistema necesarias para compilar librerías
RUN apt-get update && apt-get install -y build-essential

# Copia e instala Gunicorn y las librerías (incluyendo sentence-transformers)
COPY requirements.txt /app/
RUN pip install --no-cache-dir gunicorn
RUN pip install --no-cache-dir -r requirements.txt

# ==============================
# STAGE 2: Imagen Final (Ligera)
# ==============================
FROM python:3.11-slim

# Establece el directorio de trabajo final
WORKDIR /app

# Copia solo las librerías instaladas desde la etapa 'builder'
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copia los archivos de código de tu proyecto
COPY . /app/

# Ejecuta collectstatic
RUN python manage.py collectstatic --no-input

# Exponer el puerto por defecto de Fly.io
EXPOSE 8080

# Comando de inicio: Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "core.wsgi:application"]