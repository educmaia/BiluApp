-- init.sql
CREATE SCHEMA IF NOT EXISTS licitacoes;

CREATE TABLE licitacoes.conhecimentos (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(500) NOT NULL,
    pergunta TEXT NOT NULL,
    resposta TEXT NOT NULL,
    modalidade VARCHAR(50),
    fase VARCHAR(50),
    tags TEXT[],
    tags_automaticas TEXT[],
    autor VARCHAR(100) NOT NULL,
    campus VARCHAR(50) DEFAULT 'Capivari',
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    votos_positivos INTEGER DEFAULT 0,
    votos_negativos INTEGER DEFAULT 0,
    visualizacoes INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'novo',
    validado_por VARCHAR(100),
    data_validacao TIMESTAMP,
    FULLTEXT INDEX idx_busca (titulo, pergunta, resposta)
);

CREATE TABLE licitacoes.comentarios (
    id SERIAL PRIMARY KEY,
    conhecimento_id INTEGER REFERENCES licitacoes.conhecimentos(id),
    autor VARCHAR(100) NOT NULL,
    cargo VARCHAR(100),
    texto TEXT NOT NULL,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tipo VARCHAR(20) DEFAULT 'comentario',
    votos INTEGER DEFAULT 0,
    resposta_para INTEGER REFERENCES licitacoes.comentarios(id)
);

-- Substituir FULLTEXT INDEX por:
CREATE INDEX idx_busca_titulo ON licitacoes.conhecimentos USING gin(to_tsvector('portuguese', titulo));
CREATE INDEX idx_busca_pergunta ON licitacoes.conhecimentos USING gin(to_tsvector('portuguese', pergunta));
CREATE INDEX idx_busca_resposta ON licitacoes.conhecimentos USING gin(to_tsvector('portuguese', resposta));