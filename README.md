# 🎓 WSS - Video Platform

Plataforma de cursos em vídeo desenvolvida com Django + Django REST Framework.

## 🚀 Tecnologias

- **Backend**: Django 5.2 + Django REST Framework
- **Database**: PostgreSQL
- **Cache/Queue**: Redis
- **Task Queue**: Celery
- **Storage**: AWS S3 / Minio
- **Monitoring**: Sentry (Error tracking & Performance)
- **Containerization**: Docker + Docker Compose

## 📁 Estrutura do Projeto

```
wss-backend-v0/
├── backend/                # Aplicação Django
│   ├── apps/              # Apps modulares
│   │   ├── users/         # Gestão de usuários
│   │   ├── courses/       # Gestão de cursos
│   │   ├── videos/        # Gestão de vídeos
│   │   ├── enrollments/   # Matrículas e progresso
│   │   └── core/          # Utilidades compartilhadas
│   ├── config/            # Configurações Django
│   │   └── settings/      # Settings por ambiente
│   ├── requirements.txt   # Dependências Python
│   └── Dockerfile         # Imagem Docker
├── docker-compose.yml     # Orquestração de containers
├── .env.example           # Template de variáveis de ambiente
└── README.md
```


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
```

2. **Configure as variáveis de ambiente**
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

3. **Inicie os containers**
```bash
docker-compose up -d
```

4. **Execute as migrações**
```bash
docker-compose exec backend python manage.py migrate
```

5. **Acesse a aplicação**
- API: http://localhost:8000/api/
- Admin: http://localhost:8000/admin/
- API Docs: http://localhost:8000/api/docs/


## 📜 API de Certificados

Sistema completo de geração e validação de certificados de conclusão de curso.

### Endpoints Disponíveis

#### 1. Listar Certificados do Usuário
```http
GET /api/certificates/
Authorization: Bearer {token}
```
Lista todos os certificados do usuário autenticado com paginação.

**Response (200 OK):**
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 2,
      "certificate_code": "WSS-2026-PD0UL3",
      "student_name": "Aluno Teste",
      "course_title": "Curso Teste Certificados",
      "instructor_name": "Instrutor Teste",
      "completion_date": "2026-03-28",
      "pdf_url": "http://localhost:5600/media/certificates/2026/03/WSS-2026-PD0UL3.pdf",
      "is_valid": true
    }
  ]
}
```

#### 2. Detalhes do Certificado
```http
GET /api/certificates/{id}/
Authorization: Bearer {token}
```
Retorna detalhes de um certificado específico do usuário.

#### 3. Download do PDF
```http
GET /api/certificates/{id}/download/
Authorization: Bearer {token}
```
Download direto do arquivo PDF do certificado (5-10 KB).

**Response Headers:**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="certificate_WSS-2026-PD0UL3.pdf"
```

#### 4. Validar Propriedade (Autenticado)
```http
POST /api/certificates/{id}/validate/
Authorization: Bearer {token}
Content-Type: application/json

{}
```
Valida se o certificado pertence ao usuário autenticado.

**Response (200 OK):**
```json
{
  "valid": true,
  "message": "Certificate belongs to you",
  "certificate_code": "WSS-2026-PD0UL3"
}
```

#### 5. Validação Pública por Código
```http
GET /api/certificates/validate/{certificate_code}/
```
**Endpoint público** (sem autenticação) para validar um certificado pelo código.

**Exemplo:**
```http
GET /api/certificates/validate/WSS-2026-PD0UL3/
```

**Response (200 OK):**
```json
{
  "valid": true,
  "message": "Certificate is valid",
  "certificate_code": "WSS-2026-PD0UL3",
  "student_name": "Aluno Teste"
}
```

### Autenticação

A maioria dos endpoints requer autenticação JWT:

1. **Obter token:**
```http
POST /api/auth/token/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "senha123"
}
```

2. **Usar o token:**
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Geração Automática

Certificados são gerados automaticamente quando:
- Usuário completa um curso (enrollment.completed = True)
- Via signal `post_save` no modelo `Enrollment`
- PDF gerado em background com ReportLab
- Armazenado em: `media/certificates/{year}/{month}/{code}.pdf`

### Performance

- **Response Time**: 20-40ms média
- **SQL Queries**: 1-3 por request (otimizado com select_related)
- **PDF Size**: ~5-10 KB por certificado
- **Formato**: A4 Landscape, 300 DPI


## 🧪 Testes

### Testes Postman
API de certificados validada com 28 testes automatizados:
- ✅ Request 1 (List): 4/4 testes
- ✅ Request 2 (Details): 6/6 testes
- ✅ Request 3 (Download): 5/5 testes
- ✅ Request 4 (Validate): 6/6 testes
- ✅ Request 5 (Public): 7/7 testes

**Total: 28/28 testes passando (100%)**

[Deixar a collection no final]
[Implementar testes automatizados]


## � Monitoramento e Rastreamento de Erros

### Sentry Integration

O projeto utiliza **Sentry** para monitoramento de erros em tempo real e rastreamento de performance.

#### Funcionalidades

- **Error Tracking**: Captura automática de exceções não tratadas
- **Performance Monitoring**: Rastreamento de transações e queries lentas
- **Release Tracking**: Versionamento de deploys para rastreabilidade
- **Environment Separation**: Ambientes isolados (development/staging/production)
- **PII Filtering**: Remoção automática de dados sensíveis (LGPD compliance)

#### Configuração

1. **Obtenha seu DSN do Sentry:**
   - Acesse https://sentry.io
   - Crie um novo projeto Django
   - Copie o DSN fornecido

2. **Configure as variáveis de ambiente:**
```bash
# .env ou .env.local
SENTRY_DSN=https://your-key@o123456.ingest.sentry.io/789012
ENVIRONMENT=development  # production | staging | development
RELEASE_VERSION=1.0.0
```

3. **Integrado automaticamente com:**
   - Django (views, middlewares, signals)
   - Redis (cache operations)
   - Celery (background tasks)

#### Dados Filtrados (Segurança)

O sistema filtra automaticamente dados sensíveis antes de enviar ao Sentry:
- Headers: `Authorization`, `Cookie`, `X-Api-Key`
- Request data: `password`, `token`, `secret`, `cpf`
- Configuração: `send_default_pii=False`

#### Performance

- **Development**: 100% de transações rastreadas (`traces_sample_rate=1.0`)
- **Production**: 10% de transações rastreadas (`traces_sample_rate=0.1`)

#### Verificação

Para verificar se a integração está funcionando:
```bash
# Em desenvolvimento, acesse qualquer endpoint inexistente
curl http://localhost:8000/api/test-404/

# Verifique no dashboard do Sentry em 5-10 segundos
```

Dashboard: https://sentry.io/organizations/your-org/issues/


## �📝 Licença

[Especificar licença]
cd wss-backend-v0