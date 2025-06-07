# backend/models.py - Corrigido
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ARRAY, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Conhecimento(Base):
    __tablename__ = "conhecimentos"
    __table_args__ = {'schema': 'licitacoes'}

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(500), nullable=False)
    pergunta = Column(Text, nullable=False)
    resposta = Column(Text, nullable=False)
    modalidade = Column(String(50))
    fase = Column(String(50))
    tags = Column(ARRAY(String), default=[])
    tags_automaticas = Column(ARRAY(String), default=[])
    autor = Column(String(100), nullable=False)
    campus = Column(String(50), default='Capivari')
    data_criacao = Column(DateTime, default=datetime.utcnow)
    votos_positivos = Column(Integer, default=0)
    votos_negativos = Column(Integer, default=0)
    visualizacoes = Column(Integer, default=0)
    status = Column(String(20), default='novo')
    validado_por = Column(String(100), nullable=True)
    data_validacao = Column(DateTime, nullable=True)

    # Relacionamento com comentários
    comentarios = relationship(
        "Comentario", back_populates="conhecimento", cascade="all, delete-orphan")


class Comentario(Base):
    __tablename__ = "comentarios"
    __table_args__ = {'schema': 'licitacoes'}

    id = Column(Integer, primary_key=True, index=True)
    conhecimento_id = Column(Integer, ForeignKey(
        'licitacoes.conhecimentos.id'), nullable=False)
    autor = Column(String(100), nullable=False)
    cargo = Column(String(100), nullable=True)
    texto = Column(Text, nullable=False)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    # comentario, duvida, correcao, exemplo
    tipo = Column(String(20), default='comentario')
    votos = Column(Integer, default=0)
    resposta_para = Column(Integer, ForeignKey(
        'licitacoes.comentarios.id'), nullable=True)

    # Relacionamentos
    conhecimento = relationship("Conhecimento", back_populates="comentarios")
    respostas = relationship("Comentario", backref="parent", remote_side=[id])


class UsuarioVoto(Base):
    __tablename__ = "usuario_votos"
    __table_args__ = {'schema': 'licitacoes'}

    id = Column(Integer, primary_key=True, index=True)
    conhecimento_id = Column(Integer, ForeignKey(
        'licitacoes.conhecimentos.id'), nullable=False)
    usuario = Column(String(100), nullable=False)
    tipo_voto = Column(String(10), nullable=False)  # 'positivo' ou 'negativo'
    data_voto = Column(DateTime, default=datetime.utcnow)

    # Constraint única para evitar múltiplos votos do mesmo usuário
    __table_args__ = (
        {'schema': 'licitacoes'},
    )


class LogAuditoria(Base):
    __tablename__ = "log_auditoria"
    __table_args__ = {'schema': 'licitacoes'}

    id = Column(Integer, primary_key=True, index=True)
    usuario = Column(String(100), nullable=False)
    # 'criar', 'editar', 'votar', 'validar'
    acao = Column(String(50), nullable=False)
    # 'conhecimento', 'comentario'
    recurso_tipo = Column(String(50), nullable=False)
    recurso_id = Column(Integer, nullable=False)
    detalhes = Column(Text, nullable=True)
    data_acao = Column(DateTime, default=datetime.utcnow)
    ip_origem = Column(String(45), nullable=True)  # Suporte IPv6


class ConfiguracaoSistema(Base):
    __tablename__ = "configuracao_sistema"
    __table_args__ = {'schema': 'licitacoes'}

    id = Column(Integer, primary_key=True, index=True)
    chave = Column(String(100), nullable=False, unique=True)
    valor = Column(Text, nullable=False)
    descricao = Column(Text, nullable=True)
    data_atualizacao = Column(DateTime, default=datetime.utcnow)
    atualizado_por = Column(String(100), nullable=False)
