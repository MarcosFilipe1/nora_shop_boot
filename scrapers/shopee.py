"""
scrapers/shopee.py — Coleta ofertas da Shopee Brasil

Programa de afiliados: affiliate.shopee.com.br
Após aprovação, gere um link qualquer no painel e copie
o valor depois de af_siteid= e cole em core/afiliados.py → SHOPEE_ID

Estratégia:
  - Busca por keyword na página de flash deals e resultados
  - Monitora produto específico por URL
  - Prioriza produtos com desconto explícito
  - Extrai item_id e shop_id para montar URL canônica
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
    'Mozilla/5.0 (Linux; Android 11; Redmi Note 10) '
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
        context = await browser.new_context(
            user_agent=UA,
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
        )
        page = await context.new_page()

        url_busca = f"https://shopee.com.br/search?keyword={keyword.replace(' ', '%20')}&order=asc&page=0&sortBy=price"
        print(f"[SHP] Buscando: {keyword}")

        try:
            await page.goto(url_busca, wait_until='domcontentloaded', timeout=35000)
            await page.wait_for_timeout(3000)  # Shopee é SPA, precisa de tempo

            items = await page.query_selector_all(
                'div[data-sqe="item"], li.shopee-search-item-result__item'
            )

            for item in items[:max_resultados]:
                try:
                    # Título
                    titulo_el = await item.query_selector(
                        'div[class*="name"], span[class*="name"]'
                    )
                    titulo = (await titulo_el.inner_text()).strip() if titulo_el else None
                    if not titulo:
                        continue

                    # URL
                    link_el = await item.query_selector('a')
                    href = await link_el.get_attribute('href') if link_el else None
                    if not href:
                        continue
                    if href.startswith('/'):
                        href = 'https://shopee.com.br' + href
                    url_prod = href.split('?')[0]

                    # Preço atual
                    preco_el = await item.query_selector(
                        'span[class*="price"]:not([class*="before"]):not([class*="original"])'
                    )
                    preco_txt = await preco_el.inner_text() if preco_el else None
                    preco_atual = _preco(preco_txt)
                    if not preco_atual:
                        continue

                    # Preço original
                    original_el = await item.query_selector(
                        'span[class*="before"], span[class*="original"]'
                    )
                    preco_original = None
                    if original_el:
                        preco_original = _preco(await original_el.inner_text())

                    # Desconto
                    desconto_pct = None
                    desc_el = await item.query_selector(
                        'div[class*="discount"], span[class*="discount"]'
                    )
                    if desc_el:
                        txt = await desc_el.inner_text()
                        match = re.search(r'(\d+)', txt)
                        if match:
                            desconto_pct = int(match.group(1))

                    if not desconto_pct and preco_original and preco_original > preco_atual:
                        desconto_pct = int((1 - preco_atual / preco_original) * 100)

                    # Filtros
                    if desconto_pct and desconto_pct < desconto_minimo:
                        continue
                    if preco_maximo and preco_atual > preco_maximo:
                        continue

                    # Imagem
                    img_el = await item.query_selector('img')
                    imagem = await img_el.get_attribute('src') if img_el else None

                    url_afiliado = gerar_link_afiliado(url_prod, 'shopee')

                    oferta = {
                        'produto_id':     None,
                        'keyword_id':     keyword_id,
                        'loja':           'shopee',
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
            print(f"[SHP] Erro na busca '{keyword}': {e}")
        finally:
            await browser.close()

    return resultados


async def buscar_flash_deals(keyword_id: int = None,
                              desconto_minimo: int = 20,
                              max_resultados: int = 15) -> list[dict]:
    """
    Busca especificamente nos Flash Deals da Shopee —
    ofertas relâmpago com desconto mais agressivo.
    """
    resultados = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA, locale='pt-BR')
        page = await context.new_page()

        print(f"[SHP] Buscando Flash Deals...")

        try:
            await page.goto(
                'https://shopee.com.br/flash_sale',
                wait_until='domcontentloaded', timeout=35000
            )
            await page.wait_for_timeout(3000)

            items = await page.query_selector_all(
                'div[class*="flash-sale-item"], li[class*="item"]'
            )

            for item in items[:max_resultados]:
                try:
                    titulo_el = await item.query_selector('div[class*="name"]')
                    titulo = (await titulo_el.inner_text()).strip() if titulo_el else None
                    if not titulo:
                        continue

                    link_el = await item.query_selector('a')
                    href = await link_el.get_attribute('href') if link_el else None
                    if not href:
                        continue
                    url_prod = ('https://shopee.com.br' + href if href.startswith('/') else href).split('?')[0]

                    preco_el = await item.query_selector('span[class*="price"]')
                    preco_atual = _preco(await preco_el.inner_text()) if preco_el else None
                    if not preco_atual:
                        continue

                    original_el = await item.query_selector('span[class*="original"]')
                    preco_original = _preco(await original_el.inner_text()) if original_el else None

                    desconto_pct = None
                    if preco_original and preco_original > preco_atual:
                        desconto_pct = int((1 - preco_atual / preco_original) * 100)

                    if desconto_pct and desconto_pct < desconto_minimo:
                        continue

                    img_el = await item.query_selector('img')
                    imagem = await img_el.get_attribute('src') if img_el else None

                    url_afiliado = gerar_link_afiliado(url_prod, 'shopee')

                    oferta = {
                        'produto_id':     None,
                        'keyword_id':     keyword_id,
                        'loja':           'shopee',
                        'titulo':         titulo,
                        'url':            url_prod,
                        'url_afiliado':   url_afiliado,
                        'preco_atual':    preco_atual,
                        'preco_original': preco_original,
                        'desconto_pct':   desconto_pct,
                        'imagem_url':     imagem,
                    }
                    resultados.append(oferta)
                    print(f"  [FLASH] {titulo[:55]} — R$ {preco_atual} ({desconto_pct}% off)")

                except Exception:
                    continue

        except Exception as e:
            print(f"[SHP] Erro ao buscar flash deals: {e}")
        finally:
            await browser.close()

    return resultados


async def monitorar_produto(url: str, produto_id: int,
                             desconto_minimo: int = 15,
                             preco_alvo: float = None) -> dict | None:

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA, locale='pt-BR')
        page = await context.new_page()

        url_limpa = url.split('?')[0]

        try:
            await page.goto(url_limpa, wait_until='domcontentloaded', timeout=35000)
            await page.wait_for_timeout(3000)

            titulo = await page.title()

            preco_el = await page.query_selector(
                'div[class*="priceSectionMain"] span[class*="price"]'
            )
            preco_atual = _preco(await preco_el.inner_text()) if preco_el else None
            if not preco_atual:
                return None

            original_el = await page.query_selector(
                'div[class*="priceSectionMain"] span[class*="original"]'
            )
            preco_original = _preco(await original_el.inner_text()) if original_el else None

            desconto_pct = None
            if preco_original and preco_original > preco_atual:
                desconto_pct = int((1 - preco_atual / preco_original) * 100)

            if desconto_pct and desconto_pct < desconto_minimo:
                return None
            if preco_alvo and preco_atual > preco_alvo:
                return None

            minimo = preco_minimo_historico(url_limpa, dias=30)
            if minimo and preco_atual > minimo * 1.05:
                return None

            img_el = await page.query_selector('div[class*="mainImage"] img')
            imagem = await img_el.get_attribute('src') if img_el else None

            url_afiliado = gerar_link_afiliado(url_limpa, 'shopee')

            return {
                'produto_id':     produto_id,
                'keyword_id':     None,
                'loja':           'shopee',
                'titulo':         titulo,
                'url':            url_limpa,
                'url_afiliado':   url_afiliado,
                'preco_atual':    preco_atual,
                'preco_original': preco_original,
                'desconto_pct':   desconto_pct,
                'imagem_url':     imagem,
            }

        except Exception as e:
            print(f"[SHP] Erro ao monitorar {url_limpa}: {e}")
            return None
        finally:
            await browser.close()


async def executar(keywords: list[dict] = None, produtos: list[dict] = None) -> list[dict]:
    todas = []

    # Flash deals primeiro (melhores ofertas do dia)
    flash = await buscar_flash_deals(desconto_minimo=20)
    for o in flash:
        hid = salvar_preco(o)
        o['historico_id'] = hid
    todas.extend(flash)

    if keywords:
        for kw in keywords:
            if kw['loja'] not in ('shopee', 'todas'):
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
            await asyncio.sleep(4)

    if produtos:
        for prod in produtos:
            if prod['loja'] != 'shopee':
                continue
            oferta = await monitorar_produto(
                url=prod['url'],
                produto_id=prod['id'],
                desconto_minimo=prod.get('desconto_minimo', 15),
                preco_alvo=prod.get('preco_alvo'),
            )
            if oferta:
                hid = salvar_preco(oferta)
                oferta['historico_id'] = hid
                todas.append(oferta)

    return todas
