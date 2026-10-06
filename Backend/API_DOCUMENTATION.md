# Cortaê API Documentation

## Base URL
```
http://localhost:5000
```

## Authentication
All protected endpoints require a JWT token stored in an HttpOnly cookie named `access_token`. The cookie is set automatically upon login.

### Login
```
POST /login
Content-Type: application/json

{
  "email": "user@example.com",
  "senha": "password123"
}
```

**Response:**
```json
{
  "mensagem": {"informacao": "Login realizado com sucesso.", "tipo": "sucesso"},
  "usuario": {
    "id_usuario": 12,
    "nome": "Barbearia Exemplo",
    "email": "barbearia@email.com",
    "telefone": "11999999999",
    "tipo": 2
  }
}
```

**User Types:**
- `0` - Administrator
- `1` - Client
- `2` - Barbearia (Barbershop)

---

## 🔐 Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/login` | User login |
| POST | `/logout` | User logout |
| POST | `/cadastro` | User registration |
| POST | `/verificar-codigo` | Email verification |
| POST | `/recuperar-senha` | Password recovery request |
| POST | `/redefinir-senha` | Password reset |
| GET | `/dados-perfil/<int:id_usuario>` | Get user profile |
| PUT | `/editar-usuario/<int:id_usuario>` | Update user profile |
| GET | `/uploads/perfil/<path:nome_arquivo>` | Serve profile photo |
| DELETE | `/excluir-foto-perfil/<int:id_usuario>` | Delete profile photo |

---

## 🏪 Barbearia (Barbershop) Endpoints

### Personalização (Barbershop Configuration)
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/barbearia/personalizacao` | Barbearia, Admin | Get barbershop config |
| POST | `/barbearia/personalizacao` | Barbearia | Create barbershop config |
| PUT | `/barbearia/personalizacao` | Barbearia | Update barbershop config |
| GET | `/barbearia/personalizacao` | Barbearia, Admin | Get barbershop config |

**Body (POST/PUT):**
```json
{
  "cor_primaria": "#FF9C08",
  "cor_secundaria": "#000000",
  "cor_terciaria": "#FFFFFF",
  "cor_texto_primario": "#000000",
  "cor_texto_secundario": "#FFFFFF",
  "historia": "Nossa história...",
  "localizacao": "Rua Exemplo, 123",
  "contato_telefone": "(11) 99999-9999",
  "contato_email": "barbearia@email.com",
  "instagram": "@barbearia",
  "chave_pix": "chave@pix.com",
  "arkhe_client_id": "client_id_arkhe",
  "arkhe_client_secret": "secret_arkhe",
  "num_funcionarios": 2,
  "funcionarios": [
    {
      "nome": "João",
      "descricao": "Barbeiro especialista",
      "dias": ["segunda", "terca"],
      "servicos": [1, 2]
    }
  ],
  "dias": {
    "segunda": {"entrada_manha": "08:00", "saida_manha": "12:00", "entrada_tarde": "14:00", "saida_tarde": "18:00"},
    "terca": {"entrada_manha": "08:00", "saida_manha": "12:00", "entrada_tarde": "14:00", "saida_tarde": "18:00"}
  }
}
```

### Serviços (Services)
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/barbearia/servicos` | Public | List barbershop services |
| POST | `/barbearia/servicos` | Barbearia | Create service |
| PUT | `/barbearia/servicos/<int:id_servico>` | Barbearia | Update service |
| DELETE | `/barbearia/servicos/<int:id_servico>` | Barbearia | Delete service |

**Body (POST/PUT):**
```json
{
  "nome": "Corte Masculino",
  "descricao": "Corte moderno",
  "preco": 25.00,
  "duracao": 30,
  "genero": "masculino"
}
```

### Funcionários (Staff) - Managed via personalizacao
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/barbearias/<int:id_barbearia>/funcionarios` | List barbershop staff |
| POST | `/barbearias/<int:id_barbearia>/funcionarios` | Create staff (via personalizacao) |
| PUT | `/barbearias/<int:id_barbearia>/funcionarios/<int:id>` | Update staff |
| DELETE | `/barbearias/<int:id_barbearia>/funcionarios/<int:id>` | Delete staff |

### Uploads
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/uploads/barbearia/<path:nome_arquivo>` | Serve barbershop images |

---

## 👤 Client Endpoints

### Agendamentos (Appointments)
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/barbearias-disponiveis` | Public | List available barbershops |
| GET | `/estabelecimento` | Public | View barbershop details |
| GET | `/barbearias/<int:id_barbearia>/funcionarios` | Public | List barbershop staff |
| POST | `/selecionar-servicos` | Client | Select services |
| GET | `/visagismo` | Client | Hair analysis |
| POST | `/agendamentos` | Client | Create appointment |
| GET | `/agendamentos/horarios` | Client | Get available time slots |
| GET | `/agendamentos` | Client | List user appointments |
| PUT | `/agendamentos/<int:id_agendamento>/cancelar` | Client | Cancel appointment |
| PUT | `/agendamentos/<int:id_agendamento>/reagendar` | Client | Reschedule appointment |
| POST | `/agendamentos/<int:id_agendamento>/avisar` | Client | Notify appointment |

**Create Appointment Body:**
```json
{
  "id_barbearia": 12,
  "ids_servicos": [5, 6],
  "data": "2026-10-15",
  "horario": "14:00",
  "id_corte": 5,
  "id_visagismo": 10,
  "id_funcionario": 33
}
```

### Visagismo (Hair Analysis)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/visagismo/cortes` | List haircut catalog |
| POST | `/visagismo/cortes` | Create haircut (admin/barbearia) |
| PUT | `/visagismo/cortes/<int:id_corte>` | Update haircut (admin/barbearia) |
| DELETE | `/visagismo/cortes/<int:id_corte>` | Delete haircut (admin/barbearia) |
| GET | `/visagismo/status` | Check OpenAI status |
| POST | `/visagismo/analisar` | Analyze face photo |
| POST | `/visagismo/salvar-foto` | Save photo without analysis |
| POST | `/visagismo/<int:id_visagismo>/simular` | Generate haircut simulation |
| GET | `/uploads/visagismo/<tipo>/<path:nome>` | Serve visagismo images |

### Agendamentos (Appointments)
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/agendamentos/horarios` | Client | Get available time slots |
| POST | `/agendamentos` | Client | Create appointment |
| GET | `/agendamentos` | Client | List user appointments |
| PUT | `/agendamentos/<int:id_agendamento>/cancelar` | Client | Cancel appointment |
| PUT | `/agendamentos/<int:id_agendamento>/reagendar` | Client | Reschedule appointment |
| POST | `/agendamentos/<int:id_agendamento>/avisar` | Client | Notify appointment |

**Create Appointment Body:**
```json
{
  "id_barbearia": 12,
  "ids_servicos": [5, 6],
  "data": "2026-10-15",
  "horario": "14:00",
  "id_corte": 5,
  "id_visagismo": 10,
  "id_funcionario": 33
}
```

---

## 💰 Financial/Payment Endpoints

### Arkhé Integration (PIX, Boleto, Cartão)
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/financeiro/conta` | Barbearia, Admin | Account info |
| GET | `/financeiro/saldo` | Barbearia, Admin | Account balance |
| GET | `/financeiro/movimentacoes` | Barbearia, Admin | Transaction history |
| GET | `/financeiro/resumo` | Barbearia, Admin | Financial summary |
| POST | `/financeiro/cobrancas/pix` | Barbearia | Create PIX charge |
| GET | `/financeiro/cobrancas/pix/<int:id_cobranca>` | Barbearia | Check PIX status |
| POST | `/financeiro/cobrancas/boleto` | Barbearia | Create boleto |
| GET | `/financeiro/cobrancas/boleto/<int:id_cobranca>` | Barbearia | Check boleto status |
| POST | `/financeiro/cobrancas/cartao` | Barbearia | Create cartão charge |
| GET | `/financeiro/cobrancas/cartao/<int:id_cobranca>` | Barbearia | Check card status |
| POST | `/financeiro/cobrancas/na-hora` | Barbearia | Confirm cash payment |
| POST | `/financeiro/webhook/arkhe` | Public | Arkhé webhook |

### Payment Flow (Agendamento Context)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/pagamentos/pix` | Generate PIX QR code for appointment |
| GET | `/pagamentos/pix/<int:id_cobranca>` | Check PIX payment status |
| GET | `/pagamentos/agendamento/<int:id_agendamento>` | List charges for appointment |

**Payment Flow:**
1. Client confirms appointment → Redirected to payment selection
2. Client chooses payment method (PIX, Boleto, Cartão, Na hora)
3. If PIX: Generate QR code → Client pays → Auto-polling checks status
4. If Boleto: Generate PDF/Code → Client pays
5. If Cartão: Redirect to Arkhé checkout
6. If Na hora: Mark as "pay on site"

---

## 🔧 Admin Endpoints

| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/listar_usuarios` | Admin | List all users |
| PUT | `/usuarios/<int:id_usuario>/status` | Admin | Toggle user status |
| GET | `/admin/usuarios` | Admin | List all users |
| PUT | `/admin/usuarios/<int:id_usuario>/status` | Admin | Toggle user status |
| GET | `/admin/cortes` | Admin, Barbearia | Manage haircut catalog |
| POST | `/admin/cortes` | Admin, Barbearia | Create haircut |
| PUT | `/admin/cortes/<int:id_corte>` | Admin, Barbearia | Update haircut |
| DELETE | `/admin/cortes/<int:id_corte>` | Admin, Barbearia | Delete haircut |
| GET | `/financeiro` | Admin, Barbearia | Financial dashboard |
| GET | `/financeiro/saldo` | Barbearia, Admin | Account balance |
| GET | `/financeiro/resumo` | Barbearia, Admin | Financial summary |
| GET | `/financeiro/movimentacoes` | Barbearia, Admin | Transaction history |
| POST | `/financeiro/cobrancas/pix` | Barbearia | Create PIX charge |
| GET | `/financeiro/cobrancas/pix/<int:id_cobranca>` | Barbearia | Check PIX status |
| POST | `/financeiro/cobrancas/boleto` | Barbearia | Create boleto |
| GET | `/financeiro/cobrancas/boleto/<int:id_cobranca>` | Barbearia | Check boleto status |
| POST | `/financeiro/cobrancas/cartao` | Barbearia | Create cartão charge |
| GET | `/financeiro/cobrancas/cartao/<int:id_cobranca>` | Barbearia | Check card status |
| POST | `/financeiro/cobrancas/na-hora` | Barbearia | Confirm cash payment |
| POST | `/financeiro/webhook/arkhe` | Public | Arkhé webhook |

---

## 🔍 Search & Utility

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/listar_usuarios` | List all users (admin) |
| PUT | `/usuarios/<int:id_usuario>/status` | Toggle user status (admin) |
| GET | `/dados-perfil/<int:id_usuario>` | Get user profile data |
| GET | `/fotos-perfil/<nome_arquivo>` | Serve profile photo |
| POST | `/cadastro` | User registration |
| POST | `/verificar-codigo` | Verify email code |

---

## ⚙️ Configuration

### Environment Variables (.env)
```env
# Security
SECRET_KEY=your-secret-key

# Database
DB_HOST=localhost
DB_NAME=CORTAE.FDB
DB_USER=SYSDBA
DB_PASSWORD=masterkey

# Email
MAIL_USER=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=465

# OpenAI
OPENAI_API_KEY=sk-...
VISAGISMO_ANALYSIS_MODEL=gpt-4o-mini
VISAGISMO_IMAGE_MODEL=gpt-image-2

# Arkhé (PIX/Banking)
ARKHE_CLIENT_ID=your_client_id
ARKHE_CLIENT_SECRET=your_client_secret
ARKHE_BASE_URL=https://arkhe-backend.zbbquj.easypanel.host
```

---

## 📋 Error Response Format
```json
{
  "mensagem": {
    "informacao": "Error description",
    "tipo": "erro|aviso|sucesso"
  },
  "detalhes": "Additional details (optional)"
}
```

---

## 📝 Status Codes
| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 500 | Internal Server Error |
| 502 | Bad Gateway (Arkhé error) |
| 503 | Service Unavailable |
