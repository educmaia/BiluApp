# metrics.py - CORRIGIDO
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import APIRouter, Response  # ✅ Import corrigido

router = APIRouter()

# Métricas
busca_counter = Counter('busca_total', 'Total de buscas realizadas')
conhecimento_criado_counter = Counter(
    'conhecimento_criado', 'Total de conhecimentos criados')
tempo_resposta_histogram = Histogram(
    'tempo_resposta_segundos', 'Tempo de resposta das buscas')


@router.get("/metrics")
async def get_metrics():
    """Endpoint para métricas do Prometheus"""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


# Funções auxiliares para incrementar métricas
def incrementar_busca():
    """Incrementa contador de buscas"""
    busca_counter.inc()


def incrementar_conhecimento_criado():
    """Incrementa contador de conhecimentos criados"""
    conhecimento_criado_counter.inc()


def registrar_tempo_resposta(tempo: float):
    """Registra tempo de resposta"""
    tempo_resposta_histogram.observe(tempo)
