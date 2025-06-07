#!/bin/bash
# setup.sh - Script de configuração do BiluAPP

set -e  # Para em caso de erro

echo "🚀 Configurando BiluAPP - Sistema de Gestão de Conhecimento IFSP"
echo "=================================================================="

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar se Docker está instalado
check_docker() {
    log_info "Verificando Docker..."
    if ! command -v docker &> /dev/null; then
        log_error "Docker não está instalado. Instale o Docker primeiro."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose não está instalado. Instale o Docker Compose primeiro."
        exit 1
    fi
    
    log_success "Docker e Docker Compose encontrados"
}

# Verificar estrutura de diretórios
check_directories() {
    log_info "Verificando estrutura de diretórios..."
    
    required_dirs=("backend" "frontend")
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            log_error "Diretório $dir não encontrado"
            exit 1
        fi
    done
    
    log_success "Estrutura de diretórios OK"
}

# Verificar e criar arquivos necessários
check_files() {
    log_info "Verificando arquivos necessários..."
    
    # Verificar se models.py não está vazio
    if [ ! -s "backend/models.py" ]; then
        log_error "❌ CRÍTICO: backend/models.py está vazio!"
        log_info "Copie o conteúdo corrigido do models.py fornecido na análise"
        exit 1
    fi
    
    # Verificar requirements.txt
    if [ ! -f "backend/requirements.txt" ]; then
        if [ -f "backend/requeriments.txt" ]; then
            log_warning "Renomeando requeriments.txt para requirements.txt"
            mv backend/requeriments.txt backend/requirements.txt
        else
            log_error "❌ CRÍTICO: requirements.txt não encontrado!"
            exit 1
        fi
    fi
    
    # Verificar Dockerfile
    if [ ! -f "backend/Dockerfile" ]; then
        log_error "❌ CRÍTICO: backend/Dockerfile não encontrado!"
        log_info "Crie o Dockerfile conforme fornecido na análise"
        exit 1
    fi
    
    # Verificar init.sql
    if [ ! -f "init.sql" ]; then
        log_error "❌ CRÍTICO: init.sql não encontrado!"
        exit 1
    fi
    
    log_success "Arquivos principais encontrados"
}

# Configurar arquivo .env
setup_env() {
    log_info "Configurando arquivo .env..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_success "Arquivo .env criado a partir do .env.example"
        else
            log_warning "Criando .env básico..."
            cat > .env << EOL
# Configurações básicas do BiluAPP
DATABASE_URL=postgresql://ifsp_user:senha_segura@postgres:5432/conhecimento_ifsp
REDIS_URL=redis://:redis_password@redis:6379/0
ELASTICSEARCH_URL=http://elasticsearch:9200
DEVELOPMENT_MODE=true
SECRET_KEY=$(openssl rand -hex 32)
CORS_ORIGINS=http://localhost,http://localhost:3000
EOL
            log_success "Arquivo .env básico criado"
        fi
    else
        log_info "Arquivo .env já existe"
    fi
}

# Verificar conectividade de rede
check_network() {
    log_info "Verificando conectividade..."
    
    # Testar se as portas necessárias estão livres
    ports=(5432 6379 9200 8000 80)
    for port in "${ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
            log_warning "Porta $port já está em uso"
        fi
    done
}

# Construir e iniciar containers
build_and_start() {
    log_info "Construindo e iniciando containers..."
    
    # Parar containers existentes
    docker-compose down 2>/dev/null || true
    
    # Construir imagens
    log_info "Construindo imagem do backend..."
    docker-compose build backend
    
    # Subir serviços de infraestrutura primeiro
    log_info "Iniciando serviços de infraestrutura..."
    docker-compose up -d postgres redis elasticsearch
    
    # Aguardar serviços ficarem prontos
    log_info "Aguardando serviços ficarem prontos..."
    sleep 30
    
    # Verificar se PostgreSQL está pronto
    max_attempts=30
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if docker-compose exec -T postgres pg_isready -U ifsp_user -d conhecimento_ifsp >/dev/null 2>&1; then
            log_success "PostgreSQL está pronto"
            break
        fi
        log_info "Aguardando PostgreSQL... (tentativa $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_error "PostgreSQL não ficou pronto a tempo"
        exit 1
    fi
    
    # Subir backend
    log_info "Iniciando backend..."
    docker-compose up -d backend
    
    # Aguardar backend ficar pronto
    sleep 10
    
    # Subir frontend
    log_info "Iniciando frontend..."
    docker-compose up -d frontend
    
    log_success "Todos os serviços iniciados!"
}

# Verificar saúde dos serviços
check_health() {
    log_info "Verificando saúde dos serviços..."
    
    # Verificar PostgreSQL
    if docker-compose exec -T postgres pg_isready -U ifsp_user -d conhecimento_ifsp >/dev/null 2>&1; then
        log_success "✅ PostgreSQL: Funcionando"
    else
        log_error "❌ PostgreSQL: Com problemas"
    fi
    
    # Verificar Redis
    if docker-compose exec -T redis redis-cli -a redis_password ping >/dev/null 2>&1; then
        log_success "✅ Redis: Funcionando"
    else
        log_error "❌ Redis: Com problemas"
    fi
    
    # Verificar Elasticsearch
    if curl -s http://localhost:9200/_cluster/health >/dev/null 2>&1; then
        log_success "✅ Elasticsearch: Funcionando"
    else
        log_warning "⚠️  Elasticsearch: Pode estar iniciando ainda"
    fi
    
    # Verificar Backend
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        log_success "✅ Backend: Funcionando"
    else
        log_error "❌ Backend: Com problemas"
    fi
    
    # Verificar Frontend
    if curl -s http://localhost/ >/dev/null 2>&1; then
        log_success "✅ Frontend: Funcionando"
    else
        log_error "❌ Frontend: Com problemas"
    fi
}

# Executar testes básicos
run_tests() {
    log_info "Executando testes básicos..."
    
    # Testar criação de tabelas
    log_info "Verificando tabelas do banco..."
    tables=$(docker-compose exec -T postgres psql -U ifsp_user -d conhecimento_ifsp -t -c "SELECT tablename FROM pg_tables WHERE schemaname = 'licitacoes';" 2>/dev/null | wc -l)
    
    if [ "$tables" -gt 0 ]; then
        log_success "✅ Tabelas criadas com sucesso"
    else
        log_error "❌ Falha ao criar tabelas"
    fi
    
    # Testar endpoints da API
    log_info "Testando endpoints da API..."
    if curl -s http://localhost:8000/ | grep -q "Base de Conhecimento"; then
        log_success "✅ API respondendo corretamente"
    else
        log_error "❌ API não está respondendo"
    fi
}

# Mostrar informações finais
show_final_info() {
    echo ""
    echo "🎉 Configuração concluída!"
    echo "========================="
    echo ""
    echo "📱 Acesse a aplicação em:"
    echo "   Frontend: http://localhost"
    echo "   API: http://localhost:8000"
    echo "   Documentação: http://localhost:8000/docs"
    echo ""
    echo "🔧 Ferramentas de administração:"
    echo "   PgAdmin: http://localhost:5050 (opcional)"
    echo "   Grafana: http://localhost:3000 (opcional)"
    echo ""
    echo "🐳 Comandos úteis do Docker:"
    echo "   Ver logs: docker-compose logs -f"
    echo "   Parar: docker-compose down"
    echo "   Reiniciar: docker-compose restart"
    echo ""
    echo "📋 Próximos passos:"
    echo "   1. Configure o Active Directory em .env"
    echo "   2. Teste a autenticação LDAP"
    echo "   3. Configure o WhatsApp Bot (opcional)"
    echo "   4. Importe dados iniciais"
    echo ""
}

# Menu principal
main() {
    case "${1:-full}" in
        "check")
            check_docker
            check_directories
            check_files
            ;;
        "build")
            build_and_start
            ;;
        "test")
            check_health
            run_tests
            ;;
        "full")
            check_docker
            check_directories
            check_files
            setup_env
            check_network
            build_and_start
            sleep 30  # Aguardar serviços estabilizarem
            check_health
            run_tests
            show_final_info
            ;;
        "help")
            echo "Uso: $0 [comando]"
            echo ""
            echo "Comandos:"
            echo "  check    - Verificar pré-requisitos"
            echo "  build    - Construir e iniciar containers"
            echo "  test     - Testar saúde dos serviços"
            echo "  full     - Configuração completa (padrão)"
            echo "  help     - Mostrar esta ajuda"
            ;;
        *)
            log_error "Comando inválido: $1"
            echo "Use '$0 help' para ver os comandos disponíveis"
            exit 1
            ;;
    esac
}

# Verificar se está sendo executado como root
if [ "$EUID" -eq 0 ]; then
    log_warning "Executando como root. Considere usar um usuário regular."
fi

# Executar função principal
main "$@"