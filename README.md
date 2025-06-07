# BiluAPP - Sistema de Gestão de Conhecimento IFSP Licitações

Sistema de base de conhecimento desenvolvido para o IFSP Campus Capivari, focado em licitações e processos administrativos com integração ao Active Directory.

## 📋 Sobre o Projeto

O BiluAPP é uma aplicação web que permite:

- Gestão de conhecimento sobre licitações
- Autenticação via Active Directory do IFSP
- Sistema de perguntas e respostas
- Classificação por modalidades e fases de processo
- Sistema de votação e validação
- Tags automáticas inteligentes
- Bot WhatsApp integrado

## 🚀 Tecnologias Utilizadas

### Backend

- **FastAPI** - Framework web moderno e rápido
- **Python 3.8+** - Linguagem de programação
- **PostgreSQL** - Banco de dados principal
- **Redis** - Cache e sessões
- **Elasticsearch** - Busca inteligente
- **python-ldap** - Integração com Active Directory
- **SQLAlchemy** - ORM para banco de dados

### Frontend

- **React.js** - Interface do usuário
- **TypeScript** - Tipagem estática
- **Material-UI** - Componentes de interface

### Infraestrutura

- **Docker** - Containerização
- **Docker Compose** - Orquestração de containers

## 📁 Estrutura do Projeto

```
BiluAPP/
├── backend/                 # API FastAPI
│   ├── main.py             # Aplicação principal
│   ├── auth.py             # Autenticação LDAP
│   ├── models.py           # Modelos de dados
│   ├── database.py         # Configuração do banco
│   ├── metrics.py          # Métricas e analytics
│   ├── whatsapp_bot.py     # Bot WhatsApp
│   └── requeriments.txt    # Dependências Python
├── frontend/               # Interface React
├── docker-compose.yml      # Configuração Docker
├── init.sql               # Scripts iniciais do banco
└── README.md              # Este arquivo
```

## 🛠️ Instalação e Configuração

### Pré-requisitos

- Python 3.8+
- Node.js 16+
- Docker e Docker Compose
- Git

### 1. Clone o repositório

```bash
git clone <url-do-repositorio>
cd BiluAPP
```

### 2. Configuração do Backend

```bash
cd backend
pip install -r requeriments.txt
```

### 3. Configuração do Banco de Dados

```bash
# Subir os serviços com Docker
docker-compose up -d postgres redis elasticsearch
```

### 4. Executar a aplicação

```bash
# Backend
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend (em outro terminal)
cd frontend
npm install
npm start
```

## 🔧 Configuração do Active Directory

O sistema está configurado para integrar com o AD do IFSP:

- **Servidor LDAP**: `ldap://ad.ifsp.edu.br`
- **Base DN**: `DC=ifsp,DC=edu,DC=br`
- **Formato de usuário**: `usuario@ifsp.edu.br`

### Campos extraídos do AD:

- Nome completo (`displayName`)
- Email institucional (`mail`)
- Departamento/Setor (`department`)

## 📊 Funcionalidades Principais

### Gestão de Conhecimento

- ✅ Criação de perguntas e respostas
- ✅ Classificação por modalidade de licitação
- ✅ Organização por fase do processo
- ✅ Sistema de tags automáticas
- ✅ Busca inteligente
- ✅ Sistema de votação (+/-)

### Modalidades Suportadas

- Pregão Eletrônico
- Dispensa Eletrônica
- Concorrência
- Inexigibilidade
- Concurso
- Leilão

### Fases do Processo

- Planejamento
- Seleção
- Contratação
- Execução

### Sistema de Tags Automáticas

Detecta automaticamente:

- Referências à Lei 14.133/2021
- Referências à Lei 8.666/1993
- Acórdãos do TCU
- Pareceres da AGU
- Artigos específicos
- Valores e prazos

## 🔐 Autenticação e Segurança

- Autenticação via Active Directory do IFSP
- Validação de credenciais em tempo real
- Tratamento robusto de erros de conexão
- Logs de auditoria
- Fechamento adequado de conexões LDAP

## 📈 Métricas e Analytics

O sistema coleta métricas sobre:

- Número de acessos
- Conhecimentos mais votados
- Usuários mais ativos
- Modalidades mais consultadas

## 🤖 Bot WhatsApp

Integração com WhatsApp para:

- Consultas rápidas
- Notificações
- Acesso móvel ao conhecimento

## 🐳 Docker

Para executar com Docker:

```bash
docker-compose up -d
```

Serviços incluídos:

- Backend FastAPI (porta 8000)
- PostgreSQL (porta 5432)
- Redis (porta 6379)
- Elasticsearch (porta 9200)

## 🧪 Testes

```bash
# Testes do backend
cd backend
pytest

# Testes do frontend
cd frontend
npm test
```

## 📝 API Documentation

Após executar o backend, a documentação da API estará disponível em:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 👥 Equipe

- **Desenvolvimento**: IFSP Campus Capivari
- **Contato**: [seu-email@ifsp.edu.br]

## 🔧 Solução de Problemas

### Problemas comuns:

1. **Erro de conexão LDAP**:

   - Verifique a conectividade com `ad.ifsp.edu.br`
   - Confirme as credenciais do usuário

2. **Erro de dependências Python**:

   ```bash
   pip install --upgrade pip
   pip install -r requeriments.txt
   ```

3. **Problemas com Docker**:
   ```bash
   docker-compose down
   docker-compose up --build
   ```

## 📞 Suporte

Para suporte técnico, entre em contato:

- Email: [suporte@ifsp.edu.br]
- Campus: IFSP Capivari
- Telefone: (19) XXXX-XXXX

---

**Desenvolvido com ❤️ pelo IFSP Campus Capivari**
