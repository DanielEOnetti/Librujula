# Dockerfile

# Usa una imagen base de Python oficial
FROM python:3.11-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instala Gunicorn y prepara el entorno
RUN pip install gunicorn

# Copia los archivos de dependencia e instálalos
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto de los archivos del proyecto (incluyendo tu código)
COPY . /app/

# Ejecuta el comando de producción de Django
RUN python manage.py collectstatic --no-input

# Exponer el puerto por defecto de Gunicorn
EXPOSE 8080

# Comando de inicio: Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "core.wsgi:application"]