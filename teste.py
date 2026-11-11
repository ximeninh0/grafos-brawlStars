"""Teste simples da API oficial do Brawl Stars."""
import json
import sys
from pathlib import Path
from urllib.parse import quote

import requests

BASE_URL = "https://api.brawlstars.com/v1"
RAIZ = Path(__file__).parent

# Nomes de jogadores têm caracteres que quebram o console padrão do Windows.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def carregar_key():
    for linha in (RAIZ / ".env").read_text().splitlines():
        if linha.startswith("BRAWL_API_KEY="):
            return linha.split("=", 1)[1].strip()
    raise RuntimeError("BRAWL_API_KEY não encontrada no .env")


sessao = requests.Session()
sessao.headers["Authorization"] = f"Bearer {carregar_key()}"


def get(caminho, **params):
    resposta = sessao.get(f"{BASE_URL}{caminho}", params=params, timeout=15)
    print(f"[{resposta.status_code}] GET {caminho}")
    if resposta.status_code == 404:
        return None
    if not resposta.ok:
        sys.exit(f"Erro da API: {resposta.text}")
    return resposta.json()


def tag_url(tag):
    # A tag começa com '#', que precisa ir codificado na URL (%23).
    return quote(tag, safe="")


def testar_api():
    # 1. Lista de brawlers
    brawlers = get("/brawlers")["items"]
    print(f"  {len(brawlers)} brawlers. Ex.: {', '.join(b['name'] for b in brawlers[:5])}\n")

    # 2. Ranking global de jogadores
    ranking = get("/rankings/global/players", limit=5)["items"]
    for jogador in ranking:
        print(f"  #{jogador['rank']} {jogador['name']} ({jogador['tag']}): {jogador['trophies']} troféus")
    print()

    # 3. Perfil do primeiro colocado
    tag = ranking[0]["tag"]
    perfil = get(f"/players/{tag_url(tag)}")
    print(f"  {perfil['name']}: {perfil['trophies']} troféus, {len(perfil['brawlers'])} brawlers\n")

    # 4. Últimas batalhas do primeiro do ranking que tenha log (alguns jogadores retornam 404)
    batalhas = []
    for jogador in ranking:
        log = get(f"/players/{tag_url(jogador['tag'])}/battlelog")
        if log:
            batalhas = log["items"]
            print(f"  {jogador['name']}: {len(batalhas)} batalhas no log")
            break
    for item in batalhas[:3]:
        batalha = item["battle"]
        print(f"  {item['battleTime']} | {batalha.get('mode')} | {batalha.get('result', 'rank ' + str(batalha.get('rank')))}")
    print()

    # 5. Rotação de eventos
    eventos = get("/events/rotation")
    print(f"  {len(eventos)} eventos ativos. Ex.: {eventos[0]['event']['mode']} em {eventos[0]['event']['map']}")


def gerar_json_brawlers():
    brawlers = get("/brawlers")["items"]
    destino = RAIZ / "brawlers.json"
    destino.write_text(json.dumps(brawlers, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {len(brawlers)} brawlers salvos em {destino}")


OPCOES = {
    "1": ("Testar a API", testar_api),
    "2": ("Gerar JSON dos brawlers", gerar_json_brawlers),
}


def main():
    for numero, (descricao, _) in OPCOES.items():
        print(f"{numero} - {descricao}")
    escolha = input("Escolha uma opção: ").strip()
    if escolha not in OPCOES:
        sys.exit("Opção inválida")
    OPCOES[escolha][1]()


if __name__ == "__main__":
    main()
