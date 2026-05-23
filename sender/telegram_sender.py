import os, sys, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.database import registrar_envio, ja_enviada_recentemente
from core.cupons import processar_cupom

TELEGRAM_TOKEN   = "8664059686:AAGhSWA1xak_amKVWfGkRuYL86vWyTogTGE"
TELEGRAM_CHAT_ID = "-1003999275496"
API_URL          = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def esc(t):
    chars = ["_","[","]","(",")",">","#","+","-","=","|","{","}",".","!","~"]
    for c in chars:
        t = str(t).replace(c, f"\\{c}")
    return t

def formatar_legenda(oferta, texto_cupom=""):
    titulo   = oferta.get("titulo", "")
    preco    = oferta.get("preco_atual", 0)
    original = oferta.get("preco_original")
    desconto = oferta.get("desconto_pct")
    link     = oferta.get("url_afiliado") or oferta.get("url", "")
    loja     = oferta.get("loja", "").upper().replace("MAGAZINELUIZA", "MAGALU")
    icons    = {"MERCADOLIVRE":"🟡","AMAZON":"📦","SHOPEE":"🧡","ALIEXPRESS":"🔴","MAGALU":"💙"}
    icon     = icons.get(loja, "🛍️")
    linhas   = [f"{icon} *{loja}* \\- OFERTA", ""]
    linhas.append(esc(titulo))
    linhas.append("")
    if original and original > preco:
        linhas.append(f"De: R$ {esc(f"{original:,.2f}".replace(",","."))} \\(original\\)")
    linhas.append(f"💰 *Por: R$ {esc(f"{preco:,.2f}".replace(",","."))}*")
    if desconto:
        linhas.append(f"🏷️ *{desconto}% OFF*")
    if texto_cupom:
        linhas.append("")
        linhas.append(esc(texto_cupom))
    linhas.append("")
    linhas.append(f"👉 [Comprar agora]({link})")
    linhas.append("")
    linhas.append("_Oferta por tempo limitado_")
    return "\n".join(linhas)

def enviar_com_imagem(texto, imagem_url, chat_id=None):
    chat = chat_id or TELEGRAM_CHAT_ID
    try:
        r = requests.post(f"{API_URL}/sendPhoto", json={
            "chat_id": chat,
            "photo": imagem_url,
            "caption": texto,
            "parse_mode": "MarkdownV2",
        }, timeout=15)
        data = r.json()
        if data.get("ok"):
            print("[TG] Enviado com imagem ✅")
            return True
        print(f"[TG] Erro foto: {data.get("description")} — tentando sem imagem")
        return False
    except Exception as e:
        print(f"[TG] Erro: {e}")
        return False

def enviar_mensagem(texto, chat_id=None):
    chat = chat_id or TELEGRAM_CHAT_ID
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": chat,
            "text": texto,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": False,
        }, timeout=10)
        data = r.json()
        if data.get("ok"):
            print("[TG] Enviado ✅")
            return True
        print(f"[TG] Erro: {data.get("description")}")
        return False
    except Exception as e:
        print(f"[TG] Erro: {e}")
        return False

def enviar_oferta(oferta, cupom=None):
    if ja_enviada_recentemente(oferta.get("url",""), horas=12):
        print(f"[TG] Ja enviada: {oferta.get("titulo","")[:40]}")
        return False
    url_final, texto_cupom = processar_cupom(
        oferta.get("url_afiliado") or oferta.get("url",""),
        oferta.get("loja",""), cupom
    )
    oferta["url_afiliado"] = url_final
    texto = formatar_legenda(oferta, texto_cupom)
    imagem = oferta.get("imagem_url")
    if imagem:
        ok = enviar_com_imagem(texto, imagem)
        if not ok:
            ok = enviar_mensagem(texto)
    else:
        ok = enviar_mensagem(texto)
    if ok:
        hid = oferta.get("historico_id")
        if hid:
            registrar_envio(hid, "telegram", TELEGRAM_CHAT_ID)
    return ok

def testar_conexao():
    return enviar_mensagem(
        "🛍️ *Nora Shop Ofertas*\n\nBot conectado e funcionando\\!\nAs melhores ofertas chegam aqui primeiro\\."
    )
