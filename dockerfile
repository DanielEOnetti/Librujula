# ==============================
# STAGE 1: Build y dependencias
# ==============================
FROM python:3.11 AS builder

# Establece el directorio de trabajo
WORKDIR /app

# 1. Actualizar el sistema e instalar dependencias de compilación
# CORRECCIÓN: Reemplazamos libatlas-base-dev (obsoleto) por libopenblas-dev (moderno)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libopenblas-dev

# Copia los archivos de dependencia e instálalos
COPY requirements.txt /app/

# Instalación optimizada sin caché
RUN pip install --no-cache-dir gunicorn
RUN pip install --no-cache-dir -r requirements.txt

# Limpieza crucial: Eliminar el caché de pip y el posible caché de PyTorch/HuggingFace
RUN rm -rf /root/.cache/pip \
    && rm -rf /root/.cache/torch \
    && rm -rf /tmp/* \
    && apt-get autoremove -y \
    && apt-get clean

# ==============================
# STAGE 2: Imagen Final (Súper Ligera)
# ==============================
FROM python:3.11-slim

# Establece el directorio de trabajo final
WORKDIR /app

# Copia solo las librerías instaladas (limpias) desde la etapa 'builder'
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copia los archivos de código de tu proyecto
COPY . /app/

# Ejecuta collectstatic
RUN python manage.py collectstatic --no-input

# Exponer el puerto por defecto de Fly.io
EXPOSE 8080

# Comando de inicio: Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "core.wsgi:application"]