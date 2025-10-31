# 🎓 WSS - Video Platform

Plataforma de cursos em vídeo desenvolvida com Django + Django REST Framework.

## 🚀 Tecnologias

- **Backend**: Django 5.2 + Django REST Framework
- **Database**: PostgreSQL
- **Cache/Queue**: Redis
- **Task Queue**: Celery
- **Storage**: AWS S3 / Minio
- **Containerization**: Docker + Docker Compose

## 📁 Estrutura do Projeto
wss-backend-v0/
├── backend/ # Aplicação Django
│ ├── apps/ # Apps modulares
│ │ ├── users/ # Gestão de usuários
│ │ ├── courses/ # Gestão de cursos
│ │ ├── videos/ # Gestão de vídeos
│ │ ├── enrollments/ # Matrículas e progresso
│ │ └── core/ # Utilidades compartilhadas
│ ├── config/ # Configurações Django
│ │ └── settings/ # Settings por ambiente
│ ├── requirements.txt # Dependências Python
│ └── Dockerfile # Imagem Docker
├── docker-compose.yml # Orquestração de containers
├── .env.example # Template de variáveis de ambiente
└── README.md


## 🛠️ Setup Local

### Pré-requisitos
- Docker & Docker Compose
- Python 3.10+
- Git

### Instalação

1. **Clone o repositório**
```bash
git clone <repo-url>
cd wss-backend-v0