"""
core/afiliados.py — Configuração e geração de links de afiliado

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PREENCHA SUAS CREDENCIAIS ABAIXO QUANDO FOREM APROVADAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MERCADO LIVRE
  1. Acesse: mercadolivre.com.br/l/afiliados-home
  2. Após aprovação, entre no painel de afiliados
  3. Vá em Conta > Perfil
  4. Copie o número que aparece como "ID de afiliado"
  Ex: '123456789'

AMAZON
  1. Acesse: associados.amazon.com.br
  2. Após aprovação, vá em Conta > IDs de rastreamento
  3. Copie sua tag — ela sempre termina em "-20"
  Ex: 'filipeoferta-20'

SHOPEE
  1. Acesse: affiliate.shopee.com.br
  2. Faça login e vá em Ferramentas > Link de Conversão
  3. Gere um link de qualquer produto
  4. No link gerado, copie o valor depois de "af_siteid="
  Ex: 'filipe123'

ALIEXPRESS
  1. Acesse: portals.aliexpress.com
  2. Após aprovação, vá em Ferramentas > Link Generator
  3. Gere um link de qualquer produto
  4. No link gerado, copie o número depois de "aff_fcid="
  Ex: '87654321'
"""

import re

# ─────────────────────────────────────────────
#  PREENCHA AQUI
# ─────────────────────────────────────────────

ML_ID          = ''   # ID numérico do painel ML           Ex: '123456789'
AMAZON_TAG     = ''   # Sua tag de associado Amazon         Ex: 'filipeoferta-20'
SHOPEE_ID      = ''   # Seu source/sub_id da Shopee         Ex: 'filipe123'
ALIEXPRESS_ID  = ''   # Número aff_fcid do AliExpress       Ex: '87654321'
MAGALU_ID      = ''   # Seu ID Parceiros Magalu                Ex: 'filipe123'   # Número aff_fcid do AliExpress       Ex: '87654321'

# ─────────────────────────────────────────────


def gerar_link_mercadolivre(url: str) -> str:
    if not ML_ID:
        return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}matt_tool=affiliates&matt_word={ML_ID}"


def gerar_link_amazon(url: str) -> str:
    if not AMAZON_TAG:
        return url
    asin = re.search(r'/dp/([A-Z0-9]{10})', url)
    if asin:
        return f"https://www.amazon.com.br/dp/{asin.group(1)}?tag={AMAZON_TAG}"
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}tag={AMAZON_TAG}"


def gerar_link_shopee(url: str) -> str:
    if not SHOPEE_ID:
        return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}af_siteid={SHOPEE_ID}"


def gerar_link_aliexpress(url: str) -> str:
    if not ALIEXPRESS_ID:
        return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}aff_fcid={ALIEXPRESS_ID}&aff_platform=portals-tool"


_GERADORES = {
    'mercadolivre': gerar_link_mercadolivre,
    'amazon':       gerar_link_amazon,
    'shopee':       gerar_link_shopee,
    'aliexpress':   gerar_link_aliexpress,
}

def gerar_link_afiliado(url: str, loja: str) -> str:
    fn = _GERADORES.get(loja)
    if fn:
        return fn(url)
    return url


if __name__ == '__main__':
    testes = [
        ('mercadolivre', 'https://www.mercadolivre.com.br/produto/exemplo'),
        ('amazon',       'https://www.amazon.com.br/dp/B08N5WRWNW'),
        ('shopee',       'https://shopee.com.br/produto-i.123.456'),
        ('aliexpress',   'https://pt.aliexpress.com/item/1234567890.html'),
    ]
    print("Links gerados (IDs vazios = link original retornado):\n")
    for loja, url in testes:
        print(f"  [{loja}]")
        print(f"  Original:  {url}")
        print(f"  Afiliado:  {gerar_link_afiliado(url, loja)}")
        print()


def gerar_link_magazineluiza(url: str) -> str:
    """
    Adiciona sua tag de afiliado Magalu.
    Cadastro: parceiros.magazineluiza.com.br
    Após aprovação, pegue seu ID em Ferramentas > Links de Afiliado
    """
    if not MAGALU_ID:
        return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}utm_source=afiliados&utm_medium=comparador&utm_campaign={MAGALU_ID}"


_GERADORES['magazineluiza'] = gerar_link_magazineluiza
