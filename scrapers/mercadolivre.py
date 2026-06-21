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

async def buscar_por_keyword(keyword, keyword_id=None, desconto_minimo=15, preco_maximo=None, max_resultados=48):
    resultados = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA, locale="pt-BR", timezone_id="America/Sao_Paulo")
        page = await context.new_page()
        url = f"https://www.mercadolivre.com.br/ofertas?q={keyword.replace(' ', '+')}&container_id=MLBoffers-gp1-today"
        print(f"[ML] Buscando: {keyword}")
        try:
            await page.goto(url, wait_until="networkidle", timeout=40000)
            await page.wait_for_timeout(3000)
            items = await page.query_selector_all("div.poly-card")
            for item in items[:max_resultados]:
                try:
                    titulo_el = await item.query_selector("p.poly-component__title-wrapper a, a.poly-component__title")
                    if not titulo_el:
                        titulo_el = await item.query_selector("a[class*='title'], p[class*='title']")
                    titulo = (await titulo_el.inner_text()).strip() if titulo_el else None
                    if not titulo: continue
                    link_el = await item.query_selector("a[href*='mercadolivre'], a[href*='MLB']")
                    if not link_el:
                        link_el = await item.query_selector("a")
                    href = await link_el.get_attribute("href") if link_el else None
                    if not href: continue
                    url_prod = href.split("?")[0]
                    preco_el = await item.query_selector("span.andes-money-amount__fraction")
                    preco_atual = _preco(await preco_el.inner_text()) if preco_el else None
                    if not preco_atual: continue
                    original_el = await item.query_selector("s .andes-money-amount__fraction, s span.andes-money-amount__fraction")
                    preco_original = _preco(await original_el.inner_text()) if original_el else None
                    desconto_pct = None
                    desc_el = await item.query_selector("span.promotion-item__discount, span[class*='discount']")
                    if desc_el:
                        match = re.search(r"(\d+)", await desc_el.inner_text())
                        desconto_pct = int(match.group(1)) if match else None
                    if not desconto_pct and preco_original and preco_original > preco_atual:
                        desconto_pct = int((1 - preco_atual / preco_original) * 100)
                    # Filtra por relevancia: titulo deve conter palavras-chave (ignora stopwords)
                    stopwords = {'de','do','da','com','para','sem','em','a','o','e','ou','no','na','um','uma'}
                    palavras = [p for p in keyword.lower().split() if p not in stopwords and len(p) > 2]
                    titulo_lower = titulo.lower()
                    if palavras and not all(p in titulo_lower for p in palavras): continue
                    if desconto_pct and desconto_pct < desconto_minimo: continue
                    if preco_maximo and preco_atual > preco_maximo: continue
                    img_el = await item.query_selector("img")
                    imagem = await img_el.get_attribute("src") if img_el else None
                    url_afiliado = gerar_link_afiliado(url_prod, "mercadolivre")
                    oferta = {"produto_id": None, "keyword_id": keyword_id, "loja": "mercadolivre",
                              "titulo": titulo, "url": url_prod, "url_afiliado": url_afiliado,
                              "preco_atual": preco_atual, "preco_original": preco_original,
                              "desconto_pct": desconto_pct, "imagem_url": imagem}
                    resultados.append(oferta)
                    print(f"  [+] {titulo[:55]} - R$ {preco_atual} ({desconto_pct}% off)")
                except: continue
        except Exception as e:
            print(f"[ML] Erro: {e}")
        finally:
            await browser.close()
    return resultados

async def executar(keywords=None, produtos=None):
    todas = []
    if keywords:
        for kw in keywords:
            if kw["loja"] not in ("mercadolivre", "todas"): continue
            ofertas = await buscar_por_keyword(kw["termo"], kw["id"], kw.get("desconto_minimo",15), kw.get("preco_maximo"))
            for o in ofertas:
                hid = salvar_preco(o)
                o["historico_id"] = hid
            todas.extend(ofertas)
            await asyncio.sleep(3)
    return todas
