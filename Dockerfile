# Build stage - usa una imagen slim para compilar dependencias
FROM python:3.13-slim as builder

WORKDIR /app

# Instalar dependencias de compilación solo si son necesarias
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements y instalar dependencias en un directorio específico
COPY requirements.txt .
RUN pip install --user --no-cache-dir --no-warn-script-location -r requirements.txt

# Stage final - imagen ultra ligera
FROM python:3.13-slim

WORKDIR /app

# Copiar solo las dependencias instaladas desde el builder
COPY --from=builder /root/.local /root/.local

# Copiar el código fuente
COPY . .

# Asegurar que los scripts en .local están en PATH
ENV PATH=/root/.local/bin:$PATH

# Variables de entorno por defecto (pueden sobrescribirse en docker-compose)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1

# Usuario no root para seguridad (opcional, comentado por si hay problemas de permisos)
# RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
# USER appuser

# Comando para ejecutar la aplicación
CMD ["python", "-u", "app.py"]
