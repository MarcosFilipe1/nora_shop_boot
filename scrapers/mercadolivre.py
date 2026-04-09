"""
Scraper do Mercado Livre.
Coleta ofertas por busca de keyword ou monitora URL de produto específico.
"""

import asyncio
import re
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from playwright.async_api import async_playwright
from core.database import salvar_preco, preco_minimo_historico
from core.afiliados import gerar_link_afiliado

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Linux; Android 11; Raspberry Pi 4) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Mobile Safari/537.36'
    )
}

def _limpar_preco(texto: str) -> float | None:
    if not texto:
        return None
    numeros = re.sub(r'[^\d,]', '', texto.strip()).replace(',', '.')
    try:
        return float(numeros)
    except ValueError:
        return None

async def buscar_por_keyword(keyword: str, keyword_id: int = None,
                              desconto_minimo: int = 15,
                              preco_maximo: float = None,
                              max_resultados: int = 10) -> list[dict]:
    """Busca produtos no ML por palavra-chave e retorna as ofertas válidas."""
    resultados = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=HEADERS['User-Agent'],
            locale='pt-BR',
            timezone_id='America/Sao_Paulo'
        )
        page = await context.new_page()

        url_busca = f"https://www.mercadolivre.com.br/ofertas?q={keyword.replace(' ', '+')}"
        print(f"[ML] Buscando: {keyword}")

        try:
            await page.goto(url_busca, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)

            items = await page.query_selector_all('li.promotion-item, div.poly-card')

            for item in items[:max_resultados]:
                try:
                    # Título
                    titulo_el = await item.query_selector(
                        'p.promotion-item__title, .poly-component__title'
                    )
                    titulo = (await titulo_el.inner_text()).strip() if titulo_el else None
                    if not titulo:
                        continue

                    # URL
                    link_el = await item.query_selector('a')
                    url_prod = await link_el.get_attribute('href') if link_el else None
                    if not url_prod:
                        continue
                    # Remove query string de rastreamento do ML
                    url_prod = url_prod.split('?')[0]

                    # Preço atual
                    preco_el = await item.query_selector(
                        '.andes-money-amount__fraction, '
                        '.price-tag-fraction, '
                        'span[class*="price"]'
                    )
                    preco_txt = await preco_el.inner_text() if preco_el else None
                    preco_atual = _limpar_preco(preco_txt)
                    if not preco_atual:
                        continue

                    # Preço original (riscado)
                    original_el = await item.query_selector(
                        's .andes-money-amount__fraction, '
                        '.price-tag-amount-discount .price-tag-fraction'
                    )
                    preco_original = None
                    if original_el:
                        preco_original = _limpar_preco(await original_el.inner_text())

                    # Desconto
                    desc_el = await item.query_selector(
                        '.promotion-item__discount, '
                        'span[class*="discount"]'
                    )
                    desconto_pct = None
                    if desc_el:
                        txt = await desc_el.inner_text()
                        match = re.search(r'(\d+)', txt)
                        desconto_pct = int(match.group(1)) if match else None

                    # Se não tem desconto explícito mas tem preço original, calcula
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

                    # Link afiliado
                    url_afiliado = gerar_link_afiliado(url_prod, 'mercadolivre')

                    oferta = {
                        'produto_id':     None,
                        'keyword_id':     keyword_id,
                        'loja':           'mercadolivre',
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
            print(f"[ML] Erro na busca '{keyword}': {e}")
        finally:
            await browser.close()

    return resultados


async def monitorar_produto(url: str, produto_id: int,
                             desconto_minimo: int = 15,
                             preco_alvo: float = None) -> dict | None:
    """Monitora um produto específico pelo URL e retorna oferta se válida."""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=HEADERS['User-Agent'],
            locale='pt-BR',
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)

            # Título
            titulo = await page.title()

            # Preço atual
            preco_el = await page.query_selector(
                '.andes-money-amount__fraction'
            )
            preco_atual = _limpar_preco(await preco_el.inner_text()) if preco_el else None
            if not preco_atual:
                return None

            # Preço original
            original_el = await page.query_selector(
                '.ui-pdp-price__original-value .andes-money-amount__fraction'
            )
            preco_original = _limpar_preco(await original_el.inner_text()) if original_el else None

            # Desconto
            desconto_pct = None
            if preco_original and preco_original > preco_atual:
                desconto_pct = int((1 - preco_atual / preco_original) * 100)

            # Filtros
            if desconto_pct and desconto_pct < desconto_minimo:
                return None
            if preco_alvo and preco_atual > preco_alvo:
                return None

            # Verifica mínimo histórico (só alerta se for preço baixo histórico)
            minimo = preco_minimo_historico(url, dias=30)
            if minimo and preco_atual > minimo * 1.05:
                print(f"  [~] Preço não é mínimo histórico: R$ {preco_atual} vs mínimo R$ {minimo}")
                return None

            # Imagem
            img_el = await page.query_selector('.ui-pdp-image')
            imagem = await img_el.get_attribute('src') if img_el else None

            url_afiliado = gerar_link_afiliado(url, 'mercadolivre')

            return {
                'produto_id':     produto_id,
                'keyword_id':     None,
                'loja':           'mercadolivre',
                'titulo':         titulo,
                'url':            url,
                'url_afiliado':   url_afiliado,
                'preco_atual':    preco_atual,
                'preco_original': preco_original,
                'desconto_pct':   desconto_pct,
                'imagem_url':     imagem,
            }

        except Exception as e:
            print(f"[ML] Erro ao monitorar produto {url}: {e}")
            return None
        finally:
            await browser.close()


async def executar(keywords: list[dict] = None, produtos: list[dict] = None) -> list[dict]:
    """Ponto de entrada principal: recebe listas do banco e retorna ofertas."""
    todas = []

    if keywords:
        for kw in keywords:
            if kw['loja'] not in ('mercadolivre', 'todas'):
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
            await asyncio.sleep(3)  # pausa entre buscas

    if produtos:
        for prod in produtos:
            if prod['loja'] != 'mercadolivre':
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


if __name__ == '__main__':
    # Teste rápido
    async def teste():
        from core.database import init_db
        init_db()
        keywords = [{'id': 0, 'termo': 'fone bluetooth', 'loja': 'mercadolivre',
                     'desconto_minimo': 10, 'preco_maximo': None}]
        ofertas = await executar(keywords=keywords)
        print(f"\nTotal de ofertas encontradas: {len(ofertas)}")
        for o in ofertas[:3]:
            print(f"  {o['titulo'][:50]} — R$ {o['preco_atual']}")

    asyncio.run(teste())
