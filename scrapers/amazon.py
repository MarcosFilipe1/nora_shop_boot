"""
scrapers/amazon.py — Coleta ofertas da Amazon Brasil

Programa de afiliados: associados.amazon.com.br
Após aprovação, pegue sua tag em Conta > IDs de rastreamento
e cole em core/afiliados.py → AMAZON_TAG = 'seutag-20'

Estratégia:
  - Busca por keyword na página de resultados
  - Monitora produto específico por URL
  - Prioriza produtos com badge "Oferta" ou "Mais vendido"
  - Extrai ASIN para montar URL canônica com tag de afiliado
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
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)


def _preco(texto: str) -> float | None:
    if not texto:
        return None
    # Remove R$, pontos de milhar, troca vírgula por ponto
    n = re.sub(r'[^\d,]', '', texto.strip()).replace(',', '.')
    try:
        return float(n)
    except ValueError:
        return None


def _extrair_asin(url: str) -> str | None:
    match = re.search(r'/dp/([A-Z0-9]{10})', url)
    return match.group(1) if match else None


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
            extra_http_headers={'Accept-Language': 'pt-BR,pt;q=0.9'}
        )
        page = await context.new_page()

        url_busca = f"https://www.amazon.com.br/s?k={keyword.replace(' ', '+')}&deals-widget=1"
        print(f"[AMZ] Buscando: {keyword}")

        try:
            await page.goto(url_busca, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)

            items = await page.query_selector_all(
                'div[data-component-type="s-search-result"]'
            )

            for item in items[:max_resultados]:
                try:
                    # Título
                    titulo_el = await item.query_selector(
                        'h2 span, h2 a span'
                    )
                    titulo = (await titulo_el.inner_text()).strip() if titulo_el else None
                    if not titulo:
                        continue

                    # URL e ASIN
                    link_el = await item.query_selector('h2 a')
                    href = await link_el.get_attribute('href') if link_el else None
                    if not href:
                        continue
                    if href.startswith('/'):
                        href = 'https://www.amazon.com.br' + href

                    asin = _extrair_asin(href)
                    if not asin:
                        continue
                    url_prod = f"https://www.amazon.com.br/dp/{asin}"

                    # Preço inteiro
                    preco_int_el = await item.query_selector(
                        'span.a-price-whole'
                    )
                    preco_frac_el = await item.query_selector(
                        'span.a-price-fraction'
                    )
                    if not preco_int_el:
                        continue

                    preco_int = (await preco_int_el.inner_text()).strip().replace('.', '')
                    preco_frac = (await preco_frac_el.inner_text()).strip() if preco_frac_el else '00'
                    try:
                        preco_atual = float(f"{preco_int}.{preco_frac}")
                    except ValueError:
                        continue

                    # Preço original (riscado)
                    original_el = await item.query_selector(
                        'span.a-text-price span.a-offscreen'
                    )
                    preco_original = None
                    if original_el:
                        preco_original = _preco(await original_el.inner_text())

                    # Desconto
                    desconto_pct = None
                    badge_el = await item.query_selector(
                        'span.a-badge-text, span[class*="savings"]'
                    )
                    if badge_el:
                        txt = await badge_el.inner_text()
                        match = re.search(r'(\d+)%', txt)
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
                    img_el = await item.query_selector('img.s-image')
                    imagem = await img_el.get_attribute('src') if img_el else None

                    url_afiliado = gerar_link_afiliado(url_prod, 'amazon')

                    oferta = {
                        'produto_id':     None,
                        'keyword_id':     keyword_id,
                        'loja':           'amazon',
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
            print(f"[AMZ] Erro na busca '{keyword}': {e}")
        finally:
            await browser.close()

    return resultados


async def monitorar_produto(url: str, produto_id: int,
                             desconto_minimo: int = 15,
                             preco_alvo: float = None) -> dict | None:
    asin = _extrair_asin(url)
    if not asin:
        print(f"[AMZ] ASIN não encontrado em: {url}")
        return None

    url_limpa = f"https://www.amazon.com.br/dp/{asin}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA, locale='pt-BR')
        page = await context.new_page()

        try:
            await page.goto(url_limpa, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)

            # Título
            titulo_el = await page.query_selector('#productTitle')
            titulo = (await titulo_el.inner_text()).strip() if titulo_el else 'Produto Amazon'

            # Preço
            preco_el = await page.query_selector(
                'span.a-price-whole, #priceblock_ourprice, #priceblock_dealprice'
            )
            if not preco_el:
                return None
            preco_atual = _preco(await preco_el.inner_text())
            if not preco_atual:
                return None

            # Preço original
            original_el = await page.query_selector(
                'span.a-text-price span.a-offscreen, #priceblock_saleprice'
            )
            preco_original = _preco(await original_el.inner_text()) if original_el else None

            # Desconto
            desconto_pct = None
            if preco_original and preco_original > preco_atual:
                desconto_pct = int((1 - preco_atual / preco_original) * 100)

            if desconto_pct and desconto_pct < desconto_minimo:
                return None
            if preco_alvo and preco_atual > preco_alvo:
                return None

            # Verifica mínimo histórico
            minimo = preco_minimo_historico(url_limpa, dias=30)
            if minimo and preco_atual > minimo * 1.05:
                return None

            # Imagem
            img_el = await page.query_selector('#landingImage, #imgBlkFront')
            imagem = await img_el.get_attribute('src') if img_el else None

            url_afiliado = gerar_link_afiliado(url_limpa, 'amazon')

            return {
                'produto_id':     produto_id,
                'keyword_id':     None,
                'loja':           'amazon',
                'titulo':         titulo,
                'url':            url_limpa,
                'url_afiliado':   url_afiliado,
                'preco_atual':    preco_atual,
                'preco_original': preco_original,
                'desconto_pct':   desconto_pct,
                'imagem_url':     imagem,
            }

        except Exception as e:
            print(f"[AMZ] Erro ao monitorar {url_limpa}: {e}")
            return None
        finally:
            await browser.close()


async def executar(keywords: list[dict] = None, produtos: list[dict] = None) -> list[dict]:
    todas = []

    if keywords:
        for kw in keywords:
            if kw['loja'] not in ('amazon', 'todas'):
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
            await asyncio.sleep(4)  # pausa entre buscas

    if produtos:
        for prod in produtos:
            if prod['loja'] != 'amazon':
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
