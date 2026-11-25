import json
import os
import requests

URL_RUX = "https://berzerk.com.br/collections/rux/products.json"
URL_GERAL = "https://berzerk.com.br/products.json"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
ARQUIVO_ESTADO = "berzerk_estado.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def carregar_estado():
    if os.path.exists(ARQUIVO_ESTADO):
        with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if "rux" in dados and "geral" in dados:
                return dados
    return {"rux": {}, "geral": {}}

def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)

def buscar_todos_produtos(base_url):
    catalogo = {}
    pagina = 1
    while True:
        separador = "&" if "?" in base_url else "?"
        url = f"{base_url}{separador}limit=250&page={pagina}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        dados = resp.json().get("products", [])
        
        if not dados:
            break
            
        for p in dados:
            pid = str(p["id"])
            tamanhos_disp = [v["title"] for v in p.get("variants", []) if v.get("available", False)]
            disponivel = len(tamanhos_disp) > 0
            preco = p["variants"][0]["price"] if p.get("variants") else "N/A"
            imagem = p["images"][0]["src"] if p.get("images") else ""
            
            catalogo[pid] = {
                "titulo": p["title"],
                "categoria": p.get("product_type") or "Geral",
                "url": f"https://berzerk.com.br/products/{p['handle']}",
                "preco": preco,
                "disponivel": disponivel,
                "tamanhos": ", ".join(tamanhos_disp) if tamanhos_disp else "Esgotado",
                "imagem": imagem
            }
        pagina += 1
    return catalogo

def enviar_alerta(titulo_evento, produto, destaque=False):
    if not WEBHOOK_URL:
        print("Erro: WEBHOOK_URL não configurada.")
        return
    mencao = "@everyone " if destaque else ""
    payload = {
        "content": f"{mencao}**{titulo_evento}**",
        "embeds": [
            {
                "title": produto["titulo"],
                "url": produto["url"],
                "color": 15158332 if destaque else 3447003,
                "fields": [
                    {"name": "Preço", "value": f"R$ {produto['preco']}", "inline": True},
                    {"name": "Tipo", "value": produto["categoria"], "inline": True},
                    {"name": "Tamanhos disponíveis", "value": produto["tamanhos"], "inline": False}
                ],
                "thumbnail": {"url": produto["imagem"]} if produto["imagem"] else {}
            }
        ]
    }
    requests.post(WEBHOOK_URL, json=payload, timeout=10)

def verificar_uma_vez():
    estado = carregar_estado()
    rux_atual = buscar_todos_produtos(URL_RUX)
    geral_atual = buscar_todos_produtos(URL_GERAL)

    if not estado["geral"]:
        estado["rux"] = rux_atual
        estado["geral"] = geral_atual
        salvar_estado(estado)
        return

    for pid, prod in geral_atual.items():
        eh_rux = pid in rux_atual
        tag = " (Coleção RUX)" if eh_rux else ""

        if pid not in estado["geral"]:
            enviar_alerta(f"🔥 NOVO LANÇAMENTO NA BERZERK{tag}!", prod, destaque=eh_rux)
        elif not estado["geral"][pid].get("disponivel", False) and prod["disponivel"]:
            enviar_alerta(f"♻️ RESTOCK NA BERZERK{tag}!", prod, destaque=eh_rux)

    estado["rux"] = rux_atual
    estado["geral"] = geral_atual
    salvar_estado(estado)

if __name__ == "__main__":
    verificar_uma_vez()