"""
core/formatter.py — Templates de mensagem para WhatsApp e Instagram
Suporta cupons tanto embutidos no link quanto exibidos na mensagem.
"""

def formatar_whatsapp(oferta: dict, texto_cupom: str = '') -> str:
    titulo    = oferta.get('titulo', '')
    preco     = oferta.get('preco_atual', 0)
    original  = oferta.get('preco_original')
    desconto  = oferta.get('desconto_pct')
    link      = oferta.get('url_afiliado') or oferta.get('url', '')
    loja      = oferta.get('loja', '').upper().replace('MAGAZINELUIZA', 'MAGALU')

    linhas = [f"🔥 *OFERTA {loja}*", ""]
    linhas.append(f"📦 {titulo}")
    linhas.append("")

    if original and original > preco:
        linhas.append(f"~~De: R$ {original:,.2f}~~".replace(',', '.'))
    linhas.append(f"💰 *Por: R$ {preco:,.2f}*".replace(',', '.'))

    if desconto:
        linhas.append(f"🏷️ {desconto}% OFF")

    # Bloco de cupom (só aparece se não foi embutido na URL)
    if texto_cupom:
        linhas.append("")
        linhas.append(texto_cupom)

    linhas.append("")
    linhas.append(f"👉 {link}")
    linhas.append("")
    linhas.append("_⚡ Oferta por tempo limitado!_")

    return "\n".join(linhas)


def formatar_instagram(oferta: dict, texto_cupom: str = '') -> str:
    titulo   = oferta.get('titulo', '')
    preco    = oferta.get('preco_atual', 0)
    original = oferta.get('preco_original')
    desconto = oferta.get('desconto_pct')
    loja     = oferta.get('loja', '').capitalize().replace('Magazineluiza', 'Magalu')

    linhas = [f"🔥 OFERTA {loja.upper()} 🔥", "", titulo, ""]

    if original and original > preco:
        linhas.append(f"De R$ {original:,.2f}".replace(',', '.'))
    linhas.append(f"👉 Por apenas R$ {preco:,.2f}".replace(',', '.'))

    if desconto:
        linhas.append(f"🏷️ {desconto}% de desconto!")

    if texto_cupom:
        linhas.append("")
        # Instagram não suporta negrito/markdown, limpa formatação
        linhas.append(texto_cupom.replace('*', '').replace('`', ''))

    linhas.append("")
    linhas.append("🔗 Link na bio!")
    linhas.append("")
    linhas.append(f"#oferta #promoção #desconto #{loja.lower()} #compras #economize")

    return "\n".join(linhas)
