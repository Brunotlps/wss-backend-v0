# Dockerfile - Instructions for building a Docker container image
# This file defines the environment, dependencies, and configuration needed to run your application in a container

# Base Image - Start from an existing image that contains the runtime environment
# Common choices: node:18-alpine, python:3.11-slim, openjdk:17-jre, nginx:alpine

# Set the working directory inside the container
# All subsequent commands will be executed relative to this directory
# WORKDIR /app

# Copy dependency files first (for better caching)
# Docker caches layers, so copying package files separately allows
# dependency installation to be cached even when source code changes
# COPY package*.json ./
# COPY requirements.txt ./
# COPY pom.xml ./

# Install dependencies
# This step is cached unless dependency files change
# RUN npm install
# RUN pip install -r requirements.txt
# RUN mvn dependency:resolve

# Copy application source code
# This should come after dependency installation for optimal caching
# COPY . .

# Build the application (if needed)
# RUN npm run build
# RUN python -m compileall .
# RUN mvn package

# Create a non-root user for security
# Running containers as root is a security risk
# RUN addgroup -g 1001 -S nodejs
# RUN adduser -S nextjs -u 1001
# USER nextjs

# Expose the port your application runs on
# This is documentation - it doesn't actually publish the port
# EXPOSE 3000

# Health check to verify container is running properly
# HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
#   CMD curl -f http://localhost:3000/health || exit 1

# Set environment variables
# ENV NODE_ENV=production
# ENV PORT=3000

# Define the default command to run when container starts
# Use exec form (JSON array) for better signal handling
# CMD ["npm", "start"]
# CMD ["python", "app.py"]
# CMD ["java", "-jar", "app.jar"]

# Alternative: Use ENTRYPOINT for commands that should always run
# ENTRYPOINT ["node", "server.js"]

# Imagem base Python 3.10 slim (versão leve)
FROM python:3.12-slim

# Define variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Instala dependências do sistema necessárias para PostgreSQL e Pillow
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de requirements
COPY requirements.txt /app/

# Instala as dependências Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copia todo o código da aplicação
COPY . /app/

# Expõe a porta 8000
EXPOSE 8000

# Comando padrão (será sobrescrito pelo docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]