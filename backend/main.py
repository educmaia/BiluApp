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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Modelos Pydantic


class TipoModalidade(str, Enum):
    PREGAO_ELETRONICO = "pregao_eletronico"
    DISPENSA_ELETRONICA = "dispensa_eletronica"
    CONCORRENCIA = "concorrencia"
    INEXIGIBILIDADE = "inexigibilidade"
    CONCURSO = "concurso"
    LEILAO = "leilao"


class FaseProcesso(str, Enum):
    PLANEJAMENTO = "planejamento"
    SELECAO = "selecao"
    CONTRATACAO = "contratacao"
    EXECUCAO = "execucao"


class StatusConhecimento(str, Enum):
    NOVO = "novo"
    VALIDADO = "validado"
    EM_REVISAO = "em_revisao"
    DESATUALIZADO = "desatualizado"


class ConhecimentoCreate(BaseModel):
    titulo: str
    pergunta: str
    resposta: str
    modalidade: Optional[TipoModalidade] = None
    fase: Optional[FaseProcesso] = None
    tags: List[str] = []


class ConhecimentoResponse(BaseModel):
    id: int
    titulo: str
    pergunta: str
    resposta: str
    modalidade: Optional[str]
    fase: Optional[str]
    tags: List[str]
    tags_automaticas: List[str]
    autor: str
    campus: str
    data_criacao: datetime
    votos_positivos: int
    votos_negativos: int
    visualizacoes: int
    status: str
    validado_por: Optional[str]
    data_validacao: Optional[datetime]

    class Config:
        from_attributes = True


class ComentarioCreate(BaseModel):
    texto: str
    tipo: str = "comentario"
    resposta_para: Optional[int] = None


class ComentarioResponse(BaseModel):
    id: int
    autor: str
    cargo: Optional[str]
    texto: str
    data_criacao: datetime
    tipo: str
    votos: int
    resposta_para: Optional[int]

    class Config:
        from_attributes = True


class VotoRequest(BaseModel):
    tipo_voto: str  # "positivo" ou "negativo"


# Detector de Tags Automáticas (mantendo a implementação original)


class TagDetector:
    def __init__(self):
        self.padroes = {
            'lei_14133': r'lei\s*(?:n[º°])?\s*14\.?133',
            'lei_8666': r'lei\s*(?:n[º°])?\s*8\.?666',
            'decreto_10024': r'decreto\s*(?:n[º°])?\s*10\.?024',
            'tcu': r'(?:acórdão|acordao)\s*(?:tcu\s*)?(\d+/\d{4})',
            'agu': r'parecer\s*(?:agu\s*)?(?:n[º°])?\s*(\d+/\d{4})',
            'dispensa': r'dispensa\s*(?:eletrônica|eletronica)?',
            'pregao': r'pregão\s*(?:eletrônico|eletronico)?',
            'valor_limite': r'(?:r\$|valor)\s*\d+\.?\d*',
            'prazo': r'\d+\s*dias?\s*(?:úteis|uteis|corridos)?',
            'recurso': r'recurso\s*(?:administrativo)?',
            'impugnacao': r'impugna[çc][ãa]o',
            'termo_referencia': r'termo\s*de\s*refer[êe]ncia|TR',
            'etp': r'estudo\s*t[ée]cnico\s*preliminar|ETP',
            'pesquisa_precos': r'pesquisa\s*de\s*pre[çc]os?'
        }

    def detectar_tags(self, texto: str) -> List[str]:
        tags = set()
        texto_lower = texto.lower()

        for tag, padrao in self.padroes.items():
            if re.search(padrao, texto_lower, re.IGNORECASE):
                tags.add(tag)

        # Detecta artigos citados
        artigos = re.findall(r'art(?:igo)?\s*(\d+)', texto_lower)
        for art in artigos:
            tags.add(f'art_{art}')

        # Detecta modalidades
        if 'pregão' in texto_lower or 'pregao' in texto_lower:
            tags.add('modalidade:pregao')
        if 'dispensa' in texto_lower:
            tags.add('modalidade:dispensa')

        return list(tags)


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

    # Criar tabelas
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tabelas do banco criadas com sucesso")
    except Exception as e:
        logger.error(f"Erro ao criar tabelas: {e}")

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
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
        # Tentar cache primeiro
        cache_key = f"conhecimentos:{modalidade}:{fase}:{status}:{tag}:{busca}:{limite}:{offset}"

        if redis_client:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

        # Query base
        query = db.query(ConhecimentoDB)

        # Aplicar filtros
        if modalidade:
            query = query.filter(ConhecimentoDB.modalidade == modalidade.value)

        if fase:
            query = query.filter(ConhecimentoDB.fase == fase.value)

        if status:
            query = query.filter(ConhecimentoDB.status == status.value)

        if tag:
            query = query.filter(
                or_(
                    ConhecimentoDB.tags.contains([tag]),
                    ConhecimentoDB.tags_automaticas.contains([tag])
                )
            )

        if busca:
            # Busca por texto
            busca_filter = or_(
                ConhecimentoDB.titulo.ilike(f"%{busca}%"),
                ConhecimentoDB.pergunta.ilike(f"%{busca}%"),
                ConhecimentoDB.resposta.ilike(f"%{busca}%")
            )
            query = query.filter(busca_filter)

        # Ordenação e paginação
        conhecimentos = query.order_by(
            (ConhecimentoDB.votos_positivos -
             ConhecimentoDB.votos_negativos).desc(),
            ConhecimentoDB.data_criacao.desc()
        ).offset(offset).limit(limite).all()

        # Converter para response model
        response = [ConhecimentoResponse.from_orm(c) for c in conhecimentos]

        # Cache por 5 minutos
        if redis_client:
            redis_client.setex(
                cache_key, 300, json.dumps(response, default=str))

        return response

    except Exception as e:
        logger.error(f"Erro ao listar conhecimentos: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
