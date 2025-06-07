# whatsapp_bot.py - CORRIGIDO
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
import httpx
import os
import logging
from typing import List, Dict, Any
from database import get_db
from models import Conhecimento

router = APIRouter(prefix="/whatsapp")
logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v17.0"
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "seu_token_aqui")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")


@router.post("/webhook")
async def whatsapp_webhook(data: dict, db: Session = Depends(get_db)):
    """Recebe mensagens do WhatsApp"""
    try:
        # Verificar se é uma mensagem
        if "messages" not in data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}):
            return {"status": "ok"}

        message_data = data["entry"][0]["changes"][0]["value"]["messages"][0]
        text = message_data.get("text", {}).get("body", "")
        sender = message_data.get("from", "")

        if text.startswith("/buscar"):
            query = text.replace("/buscar", "").strip()
            if query:
                # Buscar no sistema
                resultados = await buscar_conhecimento(query, db)

                # Enviar resposta
                await enviar_mensagem_whatsapp(
                    sender,
                    formatar_resultados(resultados)
                )
            else:
                await enviar_mensagem_whatsapp(
                    sender,
                    "📝 *Como usar:*\n/buscar sua pergunta aqui\n\nExemplo:\n/buscar dispensa eletrônica valor limite"
                )

        elif text.startswith("/ajuda") or text.lower() in ["oi", "ola", "olá", "help"]:
            await enviar_mensagem_whatsapp(
                sender,
                "🤖 *Bot IFSP Licitações*\n\n"
                "📋 *Comandos disponíveis:*\n"
                "/buscar [pergunta] - Buscar conhecimento\n"
                "/ajuda - Ver esta mensagem\n\n"
                "💡 *Exemplo:*\n"
                "/buscar pregão eletrônico documentos"
            )

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Erro no webhook WhatsApp: {e}")
        return {"status": "error", "message": str(e)}


async def buscar_conhecimento(query: str, db: Session) -> List[Dict[str, Any]]:
    """Busca conhecimentos no banco de dados"""
    try:
        # Busca por título, pergunta ou resposta
        resultados = db.query(Conhecimento).filter(
            or_(
                Conhecimento.titulo.ilike(f"%{query}%"),
                Conhecimento.pergunta.ilike(f"%{query}%"),
                Conhecimento.resposta.ilike(f"%{query}%"),
                Conhecimento.tags.contains([query.lower()])
            )
        ).order_by(
            (Conhecimento.votos_positivos - Conhecimento.votos_negativos).desc()
        ).limit(3).all()

        # Converter para dicionário
        return [
            {
                "id": r.id,
                "titulo": r.titulo,
                "pergunta": r.pergunta,
                "resposta": r.resposta[:200] + "..." if len(r.resposta) > 200 else r.resposta,
                "modalidade": r.modalidade,
                "votos": r.votos_positivos - r.votos_negativos
            }
            for r in resultados
        ]

    except Exception as e:
        logger.error(f"Erro na busca: {e}")
        return []


def formatar_resultados(resultados: List[Dict[str, Any]]) -> str:
    """Formata os resultados para envio via WhatsApp"""
    if not resultados:
        return "❌ *Nenhum resultado encontrado*\n\n" \
               "💡 Tente termos mais específicos como:\n" \
               "• dispensa eletrônica\n" \
               "• pregão eletrônico\n" \
               "• valor estimado\n" \
               "• documentos habilitação"

    mensagem = f"📚 *Encontrei {len(resultados)} resultado(s):*\n\n"

    for i, resultado in enumerate(resultados, 1):
        votos_emoji = "👍" if resultado["votos"] > 0 else "👎" if resultado["votos"] < 0 else "⚖️"
        modalidade = f" ({resultado['modalidade']})" if resultado["modalidade"] else ""

        mensagem += f"*{i}. {resultado['titulo']}*{modalidade}\n"
        mensagem += f"{votos_emoji} {resultado['votos']} votos\n"
        mensagem += f"📝 {resultado['resposta']}\n\n"

        if i >= 3:  # Limitar a 3 resultados
            break

    mensagem += "💻 *Acesse o sistema completo:*\nhttp://localhost:8000"
    return mensagem


async def enviar_mensagem_whatsapp(destinatario: str, mensagem: str):
    """Envia mensagem via WhatsApp Business API"""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        logger.warning("WhatsApp não configurado - token ou phone_id ausente")
        return

    try:
        url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_ID}/messages"

        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": destinatario,
            "type": "text",
            "text": {
                "body": mensagem
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                logger.info(f"Mensagem enviada para {destinatario}")
            else:
                logger.error(
                    f"Erro ao enviar mensagem: {response.status_code} - {response.text}")

    except Exception as e:
        logger.error(f"Erro ao enviar mensagem WhatsApp: {e}")


@router.get("/webhook")
async def whatsapp_verify(
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None
):
    """Verificação do webhook do WhatsApp"""
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "verify_token_123")

    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info("Webhook do WhatsApp verificado com sucesso")
        return int(hub_challenge)
    else:
        logger.warning("Falha na verificação do webhook do WhatsApp")
        return "Verification failed"
