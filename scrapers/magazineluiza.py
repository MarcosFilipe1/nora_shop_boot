"""
scrapers/magazineluiza.py — Coleta ofertas do Magazine Luiza

Programa de afiliados: Parceiros Magalu
Cadastro: parceiros.magazineluiza.com.br
Após aprovação, sua tag fica no formato: ?utm_source=afiliados&utm_medium=SEU_ID
"""

import asyncio
import re
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from playwright.async_api import async_playwright
from core.database import salvar_preco, preco_minimo_historico
from core.afiliados import gerar_link_afiliado

UA = (
    'Mozilla/5.0 (Linux; Android 11; Raspberry Pi 4) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Mobile Safari/537.36'
)


def _preco(texto: str) -> float | None:
    if not texto:
        return None
    n = re.sub(r'[^\d,]', '', texto.strip()).replace(',', '.')
    try:
        return float(n)
    except ValueError:
        return None


async def buscar_por_keyword(keyword: str, keyword_id: int = None,
                              desconto_minimo: int = 15,
                              preco_maximo: float = None,
                              max_resultados: int = 10) -> list[dict]:

    resultados = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA, locale='pt-BR',
                                            timezone_id='America/Sao_Paulo')
        page = await context.new_page()

        url_busca = (
            f"https://www.magazineluiza.com.br/busca/{keyword.replace(' ', '%20')}/"
            f"?from=submit&filters=price---0:5000"
        )
        print(f"[MAGALU] Buscando: {keyword}")

        try:
            await page.goto(url_busca, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)

            items = await page.query_selector_all(
                'li[data-testid="product-card"], div[data-testid="product-card"]'
            )

            for item in items[:max_resultados]:
                try:
                    # Título
                    titulo_el = await item.query_selector(
                        'h2[data-testid="product-title"], [data-testid="product-title"]'
                    )
                    titulo = (await titulo_el.inner_text()).strip() if titulo_el else None
                    if not titulo:
                        continue

                    # URL
                    link_el = await item.query_selector('a')
                    url_rel = await link_el.get_attribute('href') if link_el else None
                    if not url_rel:
                        continue
                    url_prod = ('https://www.magazineluiza.com.br' + url_rel
                                if url_rel.startswith('/') else url_rel)
                    url_prod = url_prod.split('?')[0]

                    # Preço atual
                    preco_el = await item.query_selector(
                        '[data-testid="price-value"], '
                        'p[data-testid="price"], '
                        'span[class*="Price"]'
                    )
                    preco_txt = await preco_el.inner_text() if preco_el else None
                    preco_atual = _preco(preco_txt)
                    if not preco_atual:
                        continue

                    # Preço original
                    original_el = await item.query_selector(
                        '[data-testid="price-original"], s, del'
                    )
                    preco_original = None
                    if original_el:
                        preco_original = _preco(await original_el.inner_text())

                    # Desconto
                    desconto_pct = None
                    desc_el = await item.query_selector('[data-testid="discount-flag"]')
                    if desc_el:
                        match = re.search(r'(\d+)', await desc_el.inner_text())
                        desconto_pct = int(match.group(1)) if match else None

                    if not desconto_pct and preco_original and preco_original > preco_atual:
                        desconto_pct = int((1 - preco_atual / preco_original) * 100)

                    if desconto_pct and desconto_pct < desconto_minimo:
                        continue
                    if preco_maximo and preco_atual > preco_maximo:
                        continue

                    # Imagem
                    img_el = await item.query_selector('img')
                    imagem = await img_el.get_attribute('src') if img_el else None

                    url_afiliado = gerar_link_afiliado(url_prod, 'magazineluiza')

                    oferta = {
                        'produto_id':     None,
                        'keyword_id':     keyword_id,
                        'loja':           'magazineluiza',
                        'titulo':         titulo,
                        'url':            url_prod,
                        'url_afiliado':   url_afiliado,
                        'preco_atual':    preco_atual,
                        'preco_original': preco_original,
                        'desconto_pct':   desconto_pct,
                        'imagem_url':     imagem,
                    }
                    resultados.append(oferta)
                    print(f"  [+] {titulo[:60]} — R$ {preco_atual} ({desconto_pct}% off)")

                except Exception as e:
                    print(f"  [!] Erro ao parsear item: {e}")
                    continue

        except Exception as e:
            print(f"[MAGALU] Erro na busca '{keyword}': {e}")
        finally:
            await browser.close()

    return resultados


async def executar(keywords: list[dict] = None, produtos: list[dict] = None) -> list[dict]:
    todas = []

    if keywords:
        for kw in keywords:
            if kw['loja'] not in ('magazineluiza', 'todas'):
                continue
            ofertas = await buscar_por_keyword(
                keyword=kw['termo'],
                keyword_id=kw['id'],
                desconto_minimo=kw.get('desconto_minimo', 15),
                preco_maximo=kw.get('preco_maximo'),
            )
            for o in ofertas:
                hid = salvar_preco(o)
                o['historico_id'] = hid
            todas.extend(ofertas)
            await asyncio.sleep(3)

    if produtos:
        for prod in produtos:
            if prod['loja'] != 'magazineluiza':
                continue
            # monitoramento de produto específico pode ser adicionado aqui
            pass

    return todas
