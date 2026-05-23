
import asyncio, re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.async_api import async_playwright
from core.database import salvar_preco
from core.afiliados import gerar_link_afiliado

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

def _preco(t):
    if not t: return None
    n = re.sub(r"[^\d,]", "", t.strip()).replace(",", ".")
    try: return float(n)
    except: return None

async def buscar_por_keyword(keyword, keyword_id=None, desconto_minimo=15, preco_maximo=None, max_resultados=10):
    resultados = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA, locale="pt-BR")
        page = await context.new_page()
        url = f"https://www.magazineluiza.com.br/busca/{keyword.replace(' ','%20')}/"
        print(f"[MAGALU] Buscando: {keyword}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=40000)
            await page.wait_for_timeout(3000)
            items = await page.query_selector_all("li[data-testid=\"product-card\"], div[data-testid=\"product-card\"], li.sc-cEvuZC")
            if not items:
                items = await page.query_selector_all("[class*=\"productCard\"], [class*=\"ProductCard\"]")
            for item in items[:max_resultados]:
                try:
                    titulo_el = await item.query_selector("h2, [data-testid=\"product-title\"], [class*=\"title\"]")
                    titulo = (await titulo_el.inner_text()).strip() if titulo_el else None
                    if not titulo: continue
                    link_el = await item.query_selector("a")
                    href = await link_el.get_attribute("href") if link_el else None
                    if not href: continue
                    url_prod = ("https://www.magazineluiza.com.br" + href if href.startswith("/") else href).split("?")[0]
                    preco_el = await item.query_selector("[data-testid=\"price-value\"], [class*=\"price\"], [class*=\"Price\"]")
                    preco_atual = _preco(await preco_el.inner_text()) if preco_el else None
                    if not preco_atual: continue
                    original_el = await item.query_selector("[data-testid=\"price-original\"], s, del")
                    preco_original = _preco(await original_el.inner_text()) if original_el else None
                    desconto_pct = None
                    if preco_original and preco_original > preco_atual:
                        desconto_pct = int((1 - preco_atual / preco_original) * 100)
                    if desconto_pct and desconto_pct < desconto_minimo: continue
                    if preco_maximo and preco_atual > preco_maximo: continue
                    img_el = await item.query_selector("img")
                    imagem = await img_el.get_attribute("src") if img_el else None
                    url_afiliado = gerar_link_afiliado(url_prod, "magazineluiza")
                    oferta = {"produto_id": None, "keyword_id": keyword_id, "loja": "magazineluiza",
                              "titulo": titulo, "url": url_prod, "url_afiliado": url_afiliado,
                              "preco_atual": preco_atual, "preco_original": preco_original,
                              "desconto_pct": desconto_pct, "imagem_url": imagem}
                    resultados.append(oferta)
                    print(f"  [+] {titulo[:55]} — R$ {preco_atual} ({desconto_pct}% off)")
                except Exception as e:
                    continue
        except Exception as e:
            print(f"[MAGALU] Erro: {e}")
        finally:
            await browser.close()
    return resultados

async def executar(keywords=None, produtos=None):
    todas = []
    if keywords:
        for kw in keywords:
            if kw["loja"] not in ("magazineluiza", "todas"): continue
            ofertas = await buscar_por_keyword(kw["termo"], kw["id"], kw.get("desconto_minimo",15), kw.get("preco_maximo"))
            for o in ofertas:
                hid = salvar_preco(o)
                o["historico_id"] = hid
            todas.extend(ofertas)
            await asyncio.sleep(3)
    return todas
