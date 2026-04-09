"""
core/cupons.py — Lógica de aplicação de cupons por loja

Cada loja tem um comportamento diferente:

  Shopee      → cupom pode ser embutido na URL (?voucher_code=CODIGO)
  Magalu      → cupom pode ser embutido na URL (?utm_coupon=CODIGO)  
  Mercado Livre → cupom só na mensagem (usuário aplica no checkout)
  Amazon      → cupom só na mensagem (usuário aplica no checkout)
  AliExpress  → cupom só na mensagem (usuário aplica no checkout)
"""

# Lojas que suportam cupom embutido na URL
SUPORTA_LINK = {'shopee', 'magazineluiza'}

# Parâmetro de URL que cada loja usa para cupom
PARAM_CUPOM = {
    'shopee':        'voucher_code',
    'magazineluiza': 'utm_coupon',
}


def aplicar_cupom_url(url: str, loja: str, codigo: str) -> str:
    """
    Embutir o cupom na URL (só para lojas que suportam).
    Retorna a URL modificada.
    """
    if loja not in SUPORTA_LINK:
        return url
    param = PARAM_CUPOM.get(loja, 'coupon')
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}{param}={codigo}"


def texto_cupom_mensagem(cupom: dict) -> str:
    """
    Gera o bloco de texto do cupom para incluir na mensagem do WhatsApp/Instagram.
    Usado quando o cupom NÃO pode ser embutido na URL.
    """
    if not cupom:
        return ''

    codigo = cupom.get('codigo', '')
    descricao = cupom.get('descricao', '')
    tipo = cupom.get('desconto_tipo', 'percentual')
    valor = cupom.get('desconto_valor')
    minimo = cupom.get('preco_minimo')
    validade = cupom.get('valido_ate', '')

    linhas = [f"🎟️ *Cupom:* `{codigo}`"]

    if descricao:
        linhas.append(f"   {descricao}")
    elif valor:
        if tipo == 'percentual':
            linhas.append(f"   {int(valor)}% de desconto")
        elif tipo == 'fixo':
            linhas.append(f"   R$ {valor:.2f} de desconto")
        elif tipo == 'frete':
            linhas.append("   Frete grátis")

    if minimo:
        linhas.append(f"   Mín: R$ {minimo:.2f}")
    if validade:
        linhas.append(f"   Válido até: {validade}")

    return '\n'.join(linhas)


def processar_cupom(url: str, loja: str, cupom: dict | None) -> tuple[str, str]:
    """
    Ponto de entrada principal.

    Retorna:
        (url_final, texto_cupom)

        url_final   → URL com cupom embutido (se a loja suportar) ou URL original
        texto_cupom → Bloco de texto para a mensagem (vazio se embutido na URL)
    """
    if not cupom or not cupom.get('ativo'):
        return url, ''

    codigo = cupom.get('codigo', '')
    aplicar_no_link = cupom.get('aplicar_no_link', 0)

    # Loja suporta + usuário quer na URL
    if aplicar_no_link and loja in SUPORTA_LINK:
        url_final = aplicar_cupom_url(url, loja, codigo)
        return url_final, ''

    # Caso contrário: cupom só na mensagem
    return url, texto_cupom_mensagem(cupom)
