# setup.ps1 - Script de configuração do BiluAPP para Windows
# Sistema de Gestão de Conhecimento IFSP

param(
    [string]$Command = "full"
)

# Cores para output no PowerShell
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    } else {
        $input | Write-Output
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Log-Info($message) {
    Write-ColorOutput Cyan "[INFO] $message"
}

function Log-Success($message) {
    Write-ColorOutput Green "[SUCCESS] $message"
}

function Log-Warning($message) {
    Write-ColorOutput Yellow "[WARNING] $message"
}

function Log-Error($message) {
    Write-ColorOutput Red "[ERROR] $message"
}

function Check-Prerequisites {
    Log-Info "Verificando pré-requisitos..."
    
    # Verificar Docker
    try {
        $dockerVersion = docker --version 2>$null
        if ($dockerVersion) {
            Log-Success "Docker encontrado: $dockerVersion"
        } else {
            throw "Docker não encontrado"
        }
    } catch {
        Log-Error "Docker não está instalado!"
        Log-Info "📥 Para instalar o Docker:"
        Log-Info "1. Baixe Docker Desktop em: https://www.docker.com/products/docker-desktop"
        Log-Info "2. Execute o instalador"
        Log-Info "3. Reinicie o computador"
        Log-Info "4. Execute este script novamente"
        return $false
    }
    
    # Verificar Docker Compose
    try {
        $composeVersion = docker-compose --version 2>$null
        if ($composeVersion) {
            Log-Success "Docker Compose encontrado: $composeVersion"
        } else {
            throw "Docker Compose não encontrado"
        }
    } catch {
        Log-Error "Docker Compose não está disponível!"
        return $false
    }
    
    return $true
}

function Check-Files {
    Log-Info "Verificando arquivos necessários..."
    
    $requiredFiles = @(
        "docker-compose.yml",
        "backend/main.py",
        "backend/auth.py",
        "init.sql"
    )
    
    $missing = @()
    foreach ($file in $requiredFiles) {
        if (!(Test-Path $file)) {
            $missing += $file
        }
    }
    
    if ($missing.Count -gt 0) {
        Log-Error "Arquivos faltando:"
        foreach ($file in $missing) {
            Log-Error "  ❌ $file"
        }
        return $false
    }
    
    # Verificar requirements.txt
    if (!(Test-Path "backend/requirements.txt")) {
        if (Test-Path "backend/requeriments.txt") {
            Log-Warning "Renomeando requeriments.txt para requirements.txt"
            Rename-Item "backend/requeriments.txt" "backend/requirements.txt"
        } else {
            Log-Error "❌ requirements.txt não encontrado!"
            return $false
        }
    }
    
    # Verificar se models.py não está vazio
    if ((Get-Content "backend/models.py" -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
        Log-Error "❌ CRÍTICO: backend/models.py está vazio!"
        Log-Info "Este arquivo precisa conter os modelos SQLAlchemy"
        return $false
    }
    
    Log-Success "Todos os arquivos necessários encontrados"
    return $true
}

function Setup-Environment {
    Log-Info "Configurando arquivo .env..."
    
    if (!(Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Log-Success "Arquivo .env criado a partir do .env.example"
        } else {
            Log-Warning "Criando .env básico..."
            $envContent = @"
# Configurações básicas do BiluAPP
DATABASE_URL=postgresql://ifsp_user:senha_segura@postgres:5432/conhecimento_ifsp
REDIS_URL=redis://:redis_password@redis:6379/0
ELASTICSEARCH_URL=http://elasticsearch:9200
DEVELOPMENT_MODE=true
SECRET_KEY=$(openssl rand -hex 32 2>$null)
CORS_ORIGINS=http://localhost,http://localhost:3000

# Configurações LDAP - IFSP
LDAP_SERVER=ldap://ad.ifsp.edu.br
LDAP_BASE_DN=DC=ifsp,DC=edu,DC=br
LDAP_DOMAIN=ifsp.edu.br

# Configurações WhatsApp (Opcional)
WHATSAPP_ENABLED=false
WHATSAPP_TOKEN=
WHATSAPP_PHONE_ID=
"@
            $envContent | Out-File -FilePath ".env" -Encoding UTF8
            Log-Success "Arquivo .env básico criado"
        }
    } else {
        Log-Info "Arquivo .env já existe"
    }
}

function Check-Ports {
    Log-Info "Verificando portas necessárias..."
    
    $ports = @(5432, 6379, 9200, 8000, 80)
    $busyPorts = @()
    
    foreach ($port in $ports) {
        $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($connection) {
            $busyPorts += $port
            Log-Warning "Porta $port já está em uso"
        }
    }
    
    if ($busyPorts.Count -gt 0) {
        Log-Warning "Algumas portas estão ocupadas. Você pode ter problemas ao iniciar os serviços."
        Log-Info "Portas ocupadas: $($busyPorts -join ', ')"
    } else {
        Log-Success "Todas as portas necessárias estão livres"
    }
}

function Start-Services {
    Log-Info "🐳 Iniciando serviços com Docker Compose..."
    
    # Parar containers existentes
    Log-Info "Parando containers existentes..."
    docker-compose down 2>$null
    
    # Iniciar serviços de infraestrutura
    Log-Info "Iniciando PostgreSQL, Redis e Elasticsearch..."
    docker-compose up -d postgres redis elasticsearch
    
    # Aguardar serviços ficarem prontos
    Log-Info "Aguardando serviços ficarem prontos (30 segundos)..."
    Start-Sleep -Seconds 30
    
    # Iniciar backend
    Log-Info "Iniciando backend..."
    docker-compose up -d backend
    
    Start-Sleep -Seconds 10
    
    # Iniciar frontend
    if (Test-Path "frontend") {
        Log-Info "Iniciando frontend..."
        docker-compose up -d frontend
    }
    
    Log-Success "🎉 Serviços iniciados!"
}

function Test-Services {
    Log-Info "🔍 Testando serviços..."
    
    # Testar PostgreSQL
    try {
        $pgTest = docker-compose exec -T postgres pg_isready -U ifsp_user -d conhecimento_ifsp 2>$null
        if ($pgTest -match "accepting connections") {
            Log-Success "✅ PostgreSQL: Funcionando"
        } else {
            Log-Error "❌ PostgreSQL: Com problemas"
        }
    } catch {
        Log-Error "❌ PostgreSQL: Não foi possível testar"
    }
    
    # Testar Backend API
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/" -UseBasicParsing -TimeoutSec 10 2>$null
        if ($response.StatusCode -eq 200) {
            Log-Success "✅ Backend API: Funcionando"
        } else {
            Log-Error "❌ Backend API: Com problemas (Status: $($response.StatusCode))"
        }
    } catch {
        Log-Warning "⚠️  Backend API: Ainda não está respondendo (pode estar iniciando)"
    }
    
    # Testar Frontend
    try {
        $response = Invoke-WebRequest -Uri "http://localhost/" -UseBasicParsing -TimeoutSec 5 2>$null
        if ($response.StatusCode -eq 200) {
            Log-Success "✅ Frontend: Funcionando"
        } else {
            Log-Error "❌ Frontend: Com problemas"
        }
    } catch {
        Log-Warning "⚠️  Frontend: Não configurado ou não está respondendo"
    }
}

function Show-FinalInfo {
    Write-Host ""
    Write-ColorOutput Green "🎉 Configuração do BiluAPP concluída!"
    Write-Host "================================="
    Write-Host ""
    Write-ColorOutput Cyan "📱 Acesse a aplicação em:"
    Write-Host "   🌐 Frontend: http://localhost"
    Write-Host "   🔧 API: http://localhost:8000"
    Write-Host "   📚 Documentação: http://localhost:8000/docs"
    Write-Host ""
    Write-ColorOutput Yellow "🐳 Comandos úteis do Docker:"
    Write-Host "   📋 Ver logs: docker-compose logs -f"
    Write-Host "   ⏹️  Parar: docker-compose down"
    Write-Host "   🔄 Reiniciar: docker-compose restart"
    Write-Host "   📊 Status: docker-compose ps"
    Write-Host ""
    Write-ColorOutput Magenta "📋 Próximos passos:"
    Write-Host "   1. ✅ Configure o Active Directory no arquivo .env"
    Write-Host "   2. 🔐 Teste a autenticação LDAP"
    Write-Host "   3. 📱 Configure o WhatsApp Bot (opcional)"
    Write-Host "   4. 📊 Importe dados iniciais"
    Write-Host "   5. 👥 Convide outros usuários"
    Write-Host ""
}

function Show-Help {
    Write-Host "BiluAPP Setup - Sistema de Gestão de Conhecimento IFSP"
    Write-Host "Uso: .\setup.ps1 [comando]"
    Write-Host ""
    Write-Host "Comandos:"
    Write-Host "  check     - Verificar pré-requisitos"
    Write-Host "  files     - Verificar arquivos necessários"
    Write-Host "  env       - Configurar arquivo .env"
    Write-Host "  start     - Iniciar serviços Docker"
    Write-Host "  test      - Testar saúde dos serviços"
    Write-Host "  full      - Configuração completa (padrão)"
    Write-Host "  help      - Mostrar esta ajuda"
    Write-Host ""
}

# Função principal
function Main {
    Write-Host ""
    Write-ColorOutput Blue "🚀 BiluAPP - Sistema de Gestão de Conhecimento IFSP"
    Write-Host "=============================================="
    Write-Host ""
    
    switch ($Command.ToLower()) {
        "check" {
            Check-Prerequisites
        }
        "files" {
            Check-Files
        }
        "env" {
            Setup-Environment
        }
        "start" {
            Start-Services
        }
        "test" {
            Test-Services
        }
        "full" {
            if (!(Check-Prerequisites)) { return }
            if (!(Check-Files)) { return }
            Setup-Environment
            Check-Ports
            Start-Services
            Start-Sleep -Seconds 20
            Test-Services
            Show-FinalInfo
        }
        "help" {
            Show-Help
        }
        default {
            Log-Error "Comando inválido: $Command"
            Show-Help
        }
    }
}

# Verificar se está executando como administrador (recomendado)
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Log-Warning "⚠️  Executando sem privilégios de administrador. Algumas funcionalidades podem não funcionar."
    Log-Info "💡 Para melhor experiência, execute o PowerShell como Administrador"
}

# Executar função principal
Main 