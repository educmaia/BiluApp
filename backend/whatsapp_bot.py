# whatsapp_bot.py
from fastapi import APIRouter
import httpx

router = APIRouter(prefix="/whatsapp")

WHATSAPP_API_URL = "https://api.whatsapp.com/v1/messages"
WHATSAPP_TOKEN = "seu_token_aqui"


@router.post("/webhook")
async def whatsapp_webhook(data: dict):
    """Recebe mensagens do WhatsApp"""
    message = data.get("message", {})
    text = message.get("text", "")
    sender = message.get("from", "")

    if text.startswith("/buscar"):
        query = text.replace("/buscar", "").strip()
        # Buscar no sistema
        resultados = await buscar_conhecimento(query)

        # Enviar resposta
        await enviar_mensagem_whatsapp(
            sender,
            formatar_resultados(resultados)
        )

    return {"status": "ok"}


async def enviar_mensagem_whatsapp(destinatario: str, mensagem: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            WHATSAPP_API_URL,
            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
            json={
                "to": destinatario,
                "type": "text",
                "text": {"body": mensagem}
            })
