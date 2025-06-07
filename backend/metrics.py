# metrics.py
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import APIRouter

router = APIRouter()

# Métricas
busca_counter = Counter('busca_total', 'Total de buscas realizadas')
conhecimento_criado_counter = Counter(
    'conhecimento_criado', 'Total de conhecimentos criados')
tempo_resposta_histogram = Histogram(
    'tempo_resposta_segundos', 'Tempo de resposta das buscas')


@router.get("/metrics")
async def get_metrics():
    return Response(generate_latest(), media_type="text/plain")
