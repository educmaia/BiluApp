# Backend do Sistema de Gestão de Conhecimento - IFSP Licitações
# Arquivo: main.py

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import re
from enum import Enum

app = FastAPI(title="Base de Conhecimento IFSP Licitações")

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos de Dados
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

class Conhecimento(BaseModel):
    id: Optional[int] = None
    titulo: str
    pergunta: str
    resposta: str
    modalidade: Optional[TipoModalidade] = None
    fase: Optional[FaseProcesso] = None
    tags: List[str] = []
    tags_automaticas: List[str] = []
    autor: str
    campus: str = "Capivari"
    data_criacao: datetime = datetime.now()
    votos_positivos: int = 0
    votos_negativos: int = 0
    visualizacoes: int = 0
    status: StatusConhecimento = StatusConhecimento.NOVO
    validado_por: Optional[str] = None
    data_validacao: Optional[datetime] = None

class Comentario(BaseModel):
    id: Optional[int] = None
    conhecimento_id: int
    autor: str
    cargo: str
    texto: str
    data: datetime = datetime.now()
    tipo: str = "comentario"  # comentario, duvida, correcao, exemplo
    votos: int = 0
    resposta_para: Optional[int] = None

class VotoRegistro(BaseModel):
    conhecimento_id: int
    usuario: str
    tipo_voto: str  # positivo, negativo

# Detector de Tags Automáticas
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

# Instância do detector
tag_detector = TagDetector()

# Banco de dados simulado (em produção, usar PostgreSQL)
conhecimentos_db: Dict[int, Conhecimento] = {}
comentarios_db: Dict[int, List[Comentario]] = {}
votos_db: Dict[str, List[int]] = {}  # usuario -> lista de ids votados
proximo_id = 1

# Endpoints

@app.get("/")
def read_root():
    return {
        "sistema": "Base de Conhecimento IFSP Licitações",
        "versao": "1.0.0",
        "campus": "Capivari"
    }

@app.post("/conhecimentos", response_model=Conhecimento)
def criar_conhecimento(conhecimento: Conhecimento):
    global proximo_id
    
    # Detecta tags automáticas
    texto_completo = f"{conhecimento.titulo} {conhecimento.pergunta} {conhecimento.resposta}"
    conhecimento.tags_automaticas = tag_detector.detectar_tags(texto_completo)
    
    # Atribui ID
    conhecimento.id = proximo_id
    proximo_id += 1
    
    # Salva no "banco"
    conhecimentos_db[conhecimento.id] = conhecimento
    comentarios_db[conhecimento.id] = []
    
    return conhecimento

@app.get("/conhecimentos", response_model=List[Conhecimento])
def listar_conhecimentos(
    modalidade: Optional[TipoModalidade] = None,
    fase: Optional[FaseProcesso] = None,
    status: Optional[StatusConhecimento] = None,
    tag: Optional[str] = None,
    busca: Optional[str] = None,
    limite: int = 20,
    offset: int = 0
):
    resultados = list(conhecimentos_db.values())
    
    # Filtros
    if modalidade:
        resultados = [k for k in resultados if k.modalidade == modalidade]
    
    if fase:
        resultados = [k for k in resultados if k.fase == fase]
    
    if status:
        resultados = [k for k in resultados if k.status == status]
    
    if tag:
        resultados = [k for k in resultados if tag in k.tags or tag in k.tags_automaticas]
    
    if busca:
        busca_lower = busca.lower()
        resultados = [
            k for k in resultados 
            if busca_lower in k.titulo.lower() or 
               busca_lower in k.pergunta.lower() or 
               busca_lower in k.resposta.lower()
        ]
    
    # Ordenação por votos
    resultados.sort(key=lambda k: k.votos_positivos - k.votos_negativos, reverse=True)
    
    # Paginação
    return resultados[offset:offset + limite]

@app.get("/conhecimentos/{conhecimento_id}", response_model=Conhecimento)
def obter_conhecimento(conhecimento_id: int):
    if conhecimento_id not in conhecimentos_db:
        raise HTTPException(status_code=404, detail="Conhecimento não encontrado")
    
    # Incrementa visualizações
    conhecimentos_db[conhecimento_id].visualizacoes += 1
    
    return conhecimentos_db[conhecimento_id]

@app.post("/conhecimentos/{conhecimento_id}/votar")
def votar_conhecimento(conhecimento_id: int, voto: VotoRegistro):
    if conhecimento_id not in conhecimentos_db:
        raise HTTPException(status_code=404, detail="Conhecimento não encontrado")
    
    # Verifica se usuário já votou
    usuario_votos = votos_db.get(voto.usuario, [])
    if conhecimento_id in usuario_votos:
        raise HTTPException(status_code=400, detail="Usuário já votou neste conhecimento")
    
    # Registra voto
    conhecimento = conhecimentos_db[conhecimento_id]
    if voto.tipo_voto == "positivo":
        conhecimento.votos_positivos += 1
    else:
        conhecimento.votos_negativos += 1
    
    # Marca que usuário votou
    if voto.usuario not in votos_db:
        votos_db[voto.usuario] = []
    votos_db[voto.usuario].append(conhecimento_id)
    
    return {"mensagem": "Voto registrado com sucesso"}

@app.post("/conhecimentos/{conhecimento_id}/validar")
def validar_conhecimento(conhecimento_id: int, validador: str, cargo: str):
    if conhecimento_id not in conhecimentos_db:
        raise HTTPException(status_code=404, detail="Conhecimento não encontrado")
    
    conhecimento = conhecimentos_db[conhecimento_id]
    conhecimento.status = StatusConhecimento.VALIDADO
    conhecimento.validado_por = f"{validador} ({cargo})"
    conhecimento.data_validacao = datetime.now()
    
    return {"mensagem": "Conhecimento validado com sucesso"}

@app.post("/conhecimentos/{conhecimento_id}/comentarios", response_model=Comentario)
def adicionar_comentario(conhecimento_id: int, comentario: Comentario):
    if conhecimento_id not in conhecimentos_db:
        raise HTTPException(status_code=404, detail="Conhecimento não encontrado")
    
    comentario.conhecimento_id = conhecimento_id
    comentario.id = len(comentarios_db.get(conhecimento_id, [])) + 1
    
    if conhecimento_id not in comentarios_db:
        comentarios_db[conhecimento_id] = []
    
    comentarios_db[conhecimento_id].append(comentario)
    
    return comentario

@app.get("/conhecimentos/{conhecimento_id}/comentarios", response_model=List[Comentario])
def listar_comentarios(conhecimento_id: int):
    if conhecimento_id not in conhecimentos_db:
        raise HTTPException(status_code=404, detail="Conhecimento não encontrado")
    
    return comentarios_db.get(conhecimento_id, [])

@app.get("/estatisticas")
def obter_estatisticas():
    total_conhecimentos = len(conhecimentos_db)
    total_validados = len([k for k in conhecimentos_db.values() if k.status == StatusConhecimento.VALIDADO])
    
    # Tags mais usadas
    todas_tags = []
    for k in conhecimentos_db.values():
        todas_tags.extend(k.tags + k.tags_automaticas)
    
    from collections import Counter
    tags_populares = Counter(todas_tags).most_common(10)
    
    return {
        "total_conhecimentos": total_conhecimentos,
        "total_validados": total_validados,
        "taxa_validacao": f"{(total_validados/total_conhecimentos*100 if total_conhecimentos > 0 else 0):.1f}%",
        "tags_populares": tags_populares,
        "modalidade_mais_comum": Counter([k.modalidade for k in conhecimentos_db.values() if k.modalidade]).most_common(1),
        "usuarios_ativos": len(votos_db)
    }

@app.get("/buscar-inteligente")
def buscar_inteligente(q: str):
    """
    Busca inteligente que retorna conhecimentos similares e sugestões
    """
    # Detecta tags na query
    tags_detectadas = tag_detector.detectar_tags(q)
    
    # Busca por texto
    resultados_texto = []
    q_lower = q.lower()
    
    for k in conhecimentos_db.values():
        score = 0
        
        # Pontuação por correspondência no título
        if q_lower in k.titulo.lower():
            score += 10
        
        # Pontuação por correspondência na pergunta
        if q_lower in k.pergunta.lower():
            score += 5
        
        # Pontuação por correspondência na resposta
        if q_lower in k.resposta.lower():
            score += 3
        
        # Pontuação por tags correspondentes
        for tag in tags_detectadas:
            if tag in k.tags or tag in k.tags_automaticas:
                score += 7
        
        if score > 0:
            resultados_texto.append({
                "conhecimento": k,
                "score": score
            })
    
    # Ordena por score
    resultados_texto.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "resultados": [r["conhecimento"] for r in resultados_texto[:10]],
        "tags_sugeridas": tags_detectadas,
        "total_encontrados": len(resultados_texto)
    }

# Dados de exemplo para demonstração
@app.on_event("startup")
def popular_dados_exemplo():
    exemplos = [
        {
            "titulo": "Como calcular o valor estimado para dispensa eletrônica em obras?",
            "pergunta": "Precisamos contratar uma reforma no laboratório. Como calcular corretamente o valor para enquadrar em dispensa eletrônica?",
            "resposta": "Para obras e serviços de engenharia, o limite para dispensa eletrônica é de R$ 108.040,82 (Decreto 11.986/2024). O cálculo deve incluir: 1) Custos diretos (materiais, mão de obra); 2) BDI (Benefícios e Despesas Indiretas); 3) Encargos sociais e trabalhistas. Importante: considerar o somatório de todas as contratações do mesmo objeto no exercício financeiro. Veja o Acórdão TCU 2.348/2023 sobre fracionamento.",
            "modalidade": TipoModalidade.DISPENSA_ELETRONICA,
            "fase": FaseProcesso.PLANEJAMENTO,
            "tags": ["obras", "valor-estimado", "bdi"],
            "autor": "Maria Santos",
            "votos_positivos": 42,
            "votos_negativos": 1,
            "status": StatusConhecimento.VALIDADO,
            "validado_por": "João Silva (Coordenador)"
        },
        {
            "titulo": "Pregão eletrônico: como proceder quando todos os licitantes são inabilitados?",
            "pergunta": "No pregão para aquisição de equipamentos de TI, todos os licitantes foram inabilitados por não atenderem às especificações técnicas. Qual o procedimento?",
            "resposta": "Conforme art. 59 da Lei 14.133/2021, quando todos os licitantes forem inabilitados, a Administração poderá fixar prazo de 3 dias úteis para apresentação de nova documentação. Procedimento: 1) Lavrar ata circunstanciada; 2) Notificar todos os licitantes; 3) Conceder prazo para saneamento; 4) Se persistir a inabilitação, declarar fracassado. O TCU orienta (Acórdão 1.795/2023) que deve-se avaliar se os requisitos não estão excessivos.",
            "modalidade": TipoModalidade.PREGAO_ELETRONICO,
            "fase": FaseProcesso.SELECAO,
            "tags": ["inabilitacao", "saneamento", "prazo-recursal"],
            "autor": "Pedro Lima",
            "votos_positivos": 38,
            "votos_negativos": 2
        }
    ]
    
    for exemplo in exemplos:
        conhecimento = Conhecimento(**exemplo)
        criar_conhecimento(conhecimento)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)