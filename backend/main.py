# backend/main.py - Corrigido
import re
import os
import logging
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_
import redis
import json
from contextlib import asynccontextmanager

# Imports locais
from database import get_db, engine
from models import Base, Conhecimento as ConhecimentoDB, Comentario as ComentarioDB, UsuarioVoto, LogAuditoria
from auth import authenticate_ad, get_current_user
from metrics import router as metrics_router
from whatsapp_bot import router as whatsapp_router

# Modelos Pydantic (mantendo os existentes do código original)
from pydantic import BaseModel
from enum import Enum

# Configuração de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('biluapp.log')
    ]
)
logger = logging.getLogger(__name__)

# Log inicial para confirmar que o sistema iniciou
logger.info("Iniciando BiluAPP com nível de log DEBUG")

# Verificação de dependências
try:
    import sqlalchemy
    logger.info(f"SQLAlchemy versão: {sqlalchemy.__version__}")
except ImportError as e:
    logger.error(f"Erro ao importar SQLAlchemy: {e}")

try:
    import fastapi
    logger.info(f"FastAPI versão: {fastapi.__version__}")
except ImportError as e:
    logger.error(f"Erro ao importar FastAPI: {e}")

# Configuração Redis
try:
    redis_client = redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True
    )
    redis_client.ping()
    logger.info("Redis conectado com sucesso")
except Exception as e:
    logger.warning(f"Redis não disponível: {e}")
    redis_client = None

# Configuração do contexto de inicialização


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Iniciando BiluAPP...")
    logger.info("Verificando conexões...")

    # Verificar conexão com o banco
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Conexão com o banco de dados estabelecida com sucesso")
    except Exception as e:
        logger.error(
            f"Erro ao conectar com o banco de dados: {e}", exc_info=True)
        raise

    # Verificar conexão com Redis
    if redis_client:
        try:
            redis_client.ping()
            logger.info("Conexão com Redis estabelecida com sucesso")
        except Exception as e:
            logger.warning(f"Redis não disponível: {e}")
    else:
        logger.warning("Redis não configurado")

    logger.info("Inicialização concluída com sucesso")
    yield

    # Shutdown
    logger.info("Finalizando BiluAPP...")

# Inicialização do FastAPI
app = FastAPI(
    title="Base de Conhecimento IFSP Licitações",
    description="Sistema de gestão de conhecimento para licitações do IFSP Campus Capivari",
    version="1.0.0",
    lifespan=lifespan
)

# Configuração CORS
origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8000",  # Adicionando a porta do backend
    "http://127.0.0.1:8000",  # Adicionando a porta do backend
]

# Middleware de logging


@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Requisição recebida: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Resposta enviada: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Erro na requisição: {str(e)}", exc_info=True)
        raise

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instância do detector de tags
tag_detector = TagDetector()

# Incluir routers
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(whatsapp_router, prefix="/api/v1")

# Função para registrar auditoria


async def registrar_auditoria(
    db: Session,
    usuario: str,
    acao: str,
    recurso_tipo: str,
    recurso_id: int,
    detalhes: str = None,
    ip_origem: str = None
):
    """Registra ação de auditoria no banco"""
    try:
        log = LogAuditoria(
            usuario=usuario,
            acao=acao,
            recurso_tipo=recurso_tipo,
            recurso_id=recurso_id,
            detalhes=detalhes,
            ip_origem=ip_origem
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"Erro ao registrar auditoria: {e}")

# Endpoints


@app.get("/")
def read_root():
    return {
        "sistema": "Base de Conhecimento IFSP Licitações",
        "versao": "1.0.0",
        "campus": "Capivari",
        "status": "ativo"
    }


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Endpoint de health check"""
    try:
        # Testar conexão com banco
        db.execute(text("SELECT 1"))

        # Testar Redis se disponível
        redis_status = "connected" if redis_client and redis_client.ping() else "disconnected"

        return {
            "status": "healthy",
            "database": "connected",
            "redis": redis_status,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.post("/api/v1/conhecimentos", response_model=ConhecimentoResponse)
async def criar_conhecimento(
    conhecimento: ConhecimentoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Criar novo conhecimento"""
    try:
        # Detecta tags automáticas
        texto_completo = f"{conhecimento.titulo} {conhecimento.pergunta} {conhecimento.resposta}"
        tags_automaticas = tag_detector.detectar_tags(texto_completo)

        # Criar conhecimento no banco
        db_conhecimento = ConhecimentoDB(
            titulo=conhecimento.titulo,
            pergunta=conhecimento.pergunta,
            resposta=conhecimento.resposta,
            modalidade=conhecimento.modalidade.value if conhecimento.modalidade else None,
            fase=conhecimento.fase.value if conhecimento.fase else None,
            tags=conhecimento.tags,
            tags_automaticas=tags_automaticas,
            autor=user["nome"],
            campus=os.getenv("CAMPUS_PADRAO", "Capivari")
        )

        db.add(db_conhecimento)
        db.commit()
        db.refresh(db_conhecimento)

        # Registrar auditoria em background
        background_tasks.add_task(
            registrar_auditoria,
            db, user["username"], "criar", "conhecimento",
            db_conhecimento.id, f"Criado: {conhecimento.titulo}"
        )

        # Limpar cache se disponível
        if redis_client:
            redis_client.delete("conhecimentos:*")

        logger.info(
            f"Conhecimento criado: ID {db_conhecimento.id} por {user['username']}")

        return ConhecimentoResponse.from_orm(db_conhecimento)

    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao criar conhecimento: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@app.get("/api/v1/conhecimentos", response_model=List[ConhecimentoResponse])
async def listar_conhecimentos(
    modalidade: Optional[TipoModalidade] = None,
    fase: Optional[FaseProcesso] = None,
    status: Optional[StatusConhecimento] = None,
    tag: Optional[str] = None,
    busca: Optional[str] = None,
    limite: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Listar conhecimentos com filtros"""
    try:
        logger.info(
            f"Recebida requisição de busca com parâmetros: busca={busca}, modalidade={modalidade}, fase={fase}, status={status}, tag={tag}")

        # Tentar cache primeiro
        cache_key = f"conhecimentos:{modalidade}:{fase}:{status}:{tag}:{busca}:{limite}:{offset}"
        logger.debug(f"Cache key: {cache_key}")

        if redis_client:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info("Retornando resultados do cache")
                return json.loads(cached)

        # Query base
        query = db.query(ConhecimentoDB)
        logger.debug("Query base criada")

        # Aplicar filtros
        if modalidade:
            query = query.filter(ConhecimentoDB.modalidade == modalidade.value)
            logger.debug(f"Filtro modalidade aplicado: {modalidade.value}")

        if fase:
            query = query.filter(ConhecimentoDB.fase == fase.value)
            logger.debug(f"Filtro fase aplicado: {fase.value}")

        if status:
            query = query.filter(ConhecimentoDB.status == status.value)
            logger.debug(f"Filtro status aplicado: {status.value}")

        if tag:
            query = query.filter(
                or_(
                    ConhecimentoDB.tags.contains([tag]),
                    ConhecimentoDB.tags_automaticas.contains([tag])
                )
            )
            logger.debug(f"Filtro tag aplicado: {tag}")

        if busca:
            # Busca por texto
            busca_filter = or_(
                ConhecimentoDB.titulo.ilike(f"%{busca}%"),
                ConhecimentoDB.pergunta.ilike(f"%{busca}%"),
                ConhecimentoDB.resposta.ilike(f"%{busca}%")
            )
            query = query.filter(busca_filter)
            logger.debug(f"Filtro de busca aplicado: {busca}")

        # Ordenação e paginação
        logger.debug("Aplicando ordenação e paginação")
        conhecimentos = query.order_by(
            (ConhecimentoDB.votos_positivos -
             ConhecimentoDB.votos_negativos).desc(),
            ConhecimentoDB.data_criacao.desc()
        ).offset(offset).limit(limite).all()

        logger.info(f"Encontrados {len(conhecimentos)} conhecimentos")

        # Converter para response model
        response = [ConhecimentoResponse.from_orm(c) for c in conhecimentos]
        logger.debug("Resposta convertida para modelo de resposta")

        # Cache por 5 minutos
        if redis_client:
            redis_client.setex(
                cache_key, 300, json.dumps(response, default=str))
            logger.debug("Resposta armazenada em cache")

        return response

    except Exception as e:
        logger.error(f"Erro ao listar conhecimentos: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno do servidor: {str(e)}"
        )


@app.get("/api/v1/conhecimentos/{conhecimento_id}", response_model=ConhecimentoResponse)
async def obter_conhecimento(
    conhecimento_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Obter conhecimento específico"""
    conhecimento = db.query(ConhecimentoDB).filter(
        ConhecimentoDB.id == conhecimento_id).first()

    if not conhecimento:
        raise HTTPException(
            status_code=404, detail="Conhecimento não encontrado")

    # Incrementar visualizações em background
    background_tasks.add_task(
        lambda: db.query(ConhecimentoDB)
        .filter(ConhecimentoDB.id == conhecimento_id)
        .update({"visualizacoes": ConhecimentoDB.visualizacoes + 1})
    )

    return ConhecimentoResponse.from_orm(conhecimento)


@app.post("/api/v1/conhecimentos/{conhecimento_id}/votar")
async def votar_conhecimento(
    conhecimento_id: int,
    voto: VotoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Votar em conhecimento"""
    # Verificar se conhecimento existe
    conhecimento = db.query(ConhecimentoDB).filter(
        ConhecimentoDB.id == conhecimento_id).first()
    if not conhecimento:
        raise HTTPException(
            status_code=404, detail="Conhecimento não encontrado")

    # Verificar se usuário já votou
    voto_existente = db.query(UsuarioVoto).filter(
        and_(
            UsuarioVoto.conhecimento_id == conhecimento_id,
            UsuarioVoto.usuario == user["username"]
        )
    ).first()

    if voto_existente:
        raise HTTPException(
            status_code=400, detail="Usuário já votou neste conhecimento")

    if voto.tipo_voto not in ["positivo", "negativo"]:
        raise HTTPException(status_code=400, detail="Tipo de voto inválido")

    # Registrar voto
    novo_voto = UsuarioVoto(
        conhecimento_id=conhecimento_id,
        usuario=user["username"],
        tipo_voto=voto.tipo_voto
    )

    db.add(novo_voto)

    # O trigger do banco irá atualizar automaticamente os contadores
    db.commit()

    # Registrar auditoria
    background_tasks.add_task(
        registrar_auditoria,
        db, user["username"], "votar", "conhecimento",
        conhecimento_id, f"Voto: {voto.tipo_voto}"
    )

    # Limpar cache
    if redis_client:
        redis_client.delete("conhecimentos:*")

    return {"message": "Voto registrado com sucesso"}


@app.get("/api/v1/estatisticas")
async def obter_estatisticas(db: Session = Depends(get_db)):
    """Obter estatísticas do sistema"""
    try:
        # Cache por 10 minutos
        cache_key = "estatisticas:geral"
        if redis_client:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

        # Consultas para estatísticas
        total_conhecimentos = db.query(ConhecimentoDB).count()
        total_validados = db.query(ConhecimentoDB).filter(
            ConhecimentoDB.status == StatusConhecimento.VALIDADO.value
        ).count()

        # Mais estatísticas...
        stats = {
            "total_conhecimentos": total_conhecimentos,
            "total_validados": total_validados,
            "taxa_validacao": f"{(total_validados/total_conhecimentos*100 if total_conhecimentos > 0 else 0):.1f}%",
            "timestamp": datetime.utcnow()
        }

        if redis_client:
            redis_client.setex(cache_key, 600, json.dumps(stats, default=str))

        return stats

    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@app.get("/api/v1/test")
async def test_endpoint():
    """Endpoint de teste simplificado"""
    logger.info("Endpoint de teste acessado")
    return {
        "status": "online",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
