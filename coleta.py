"""
coleta.py — Coleta de partidas 3v3 do Brawl Stars via API oficial.

Fluxo:
  1. Sementes: jogadores dos rankings de alguns países (/rankings/{pais}/players)
  2. BFS: para cada jogador da fila, baixa o battlelog (/players/{tag}/battlelog),
     salva as partidas 3v3 únicas e enfileira os jogadores encontrados.
  3. Tudo é salvo incrementalmente em data/raw/, então dá para parar (Ctrl+C)
     e retomar depois rodando o mesmo comando.

Uso:
  pip install requests python-dotenv tqdm
  # crie um arquivo .env com:  BRAWL_TOKEN=seu_token_aqui
  python coleta.py --max-jogadores 5000
  python coleta.py --paises global BR US MX --rps 10

Saídas (data/raw/):
  partidas.jsonl   uma partida 3v3 única por linha (+ campos _owner, _key)
  estado.json      fila e visitados da BFS (para retomar)
"""

import argparse
import json
import os
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
TOKEN = os.getenv("BRAWL_TOKEN")
BASE_URL = os.getenv("BRAWL_BASE_URL", "https://api.brawlstars.com/v1")

DIR_RAW = Path("data/raw")
ARQ_PARTIDAS = DIR_RAW / "partidas.jsonl"
ARQ_ESTADO = DIR_RAW / "estado.json"


# ----------------------------------------------------------------------------
# Cliente HTTP com rate limit e retentativas
# ----------------------------------------------------------------------------
class ClienteBrawl:
    def __init__(self, token: str, rps: float = 10.0):
        self.sessao = requests.Session()
        self.sessao.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
        self.intervalo = 1.0 / rps
        self._ultimo = 0.0

    def _esperar_vez(self):
        dt = time.monotonic() - self._ultimo
        if dt < self.intervalo:
            time.sleep(self.intervalo - dt)
        self._ultimo = time.monotonic()

    def get(self, caminho: str, tentativas: int = 5):
        """Retorna o JSON, ou None se o recurso não existir (404)."""
        url = f"{BASE_URL}{caminho}"
        espera = 1.0
        for _ in range(tentativas):
            self._esperar_vez()
            try:
                r = self.sessao.get(url, timeout=15)
            except requests.RequestException as e:
                tqdm.write(f"[rede] {e} — tentando de novo em {espera:.0f}s")
                time.sleep(espera); espera *= 2
                continue

            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            if r.status_code == 403:
                sys.exit(
                    "[403] Acesso negado. Verifique se o token está certo e se o IP "
                    "desta máquina está cadastrado na chave em developer.brawlstars.com."
                )
            if r.status_code in (429, 500, 502, 503, 504):
                tqdm.write(f"[{r.status_code}] aguardando {espera:.0f}s...")
                time.sleep(espera); espera *= 2
                continue
            tqdm.write(f"[{r.status_code}] {url}: {r.text[:200]}")
            return None
        tqdm.write(f"[desistindo] {url}")
        return None

    # Endpoints ---------------------------------------------------------------
    def ranking_jogadores(self, pais: str = "global"):
        dados = self.get(f"/rankings/{pais}/players")
        return [] if not dados else dados.get("items", [])

    def battlelog(self, tag: str):
        dados = self.get(f"/players/{quote(tag)}/battlelog")
        return [] if not dados else dados.get("items", [])


# ----------------------------------------------------------------------------
# Utilidades de partida
# ----------------------------------------------------------------------------
def eh_3v3(item: dict) -> bool:
    times = item.get("battle", {}).get("teams")
    return (
        isinstance(times, list)
        and len(times) == 2
        and all(len(t) == 3 for t in times)
    )


def chave_partida(item: dict) -> str:
    """Identificador único: horário + 6 tags ordenadas.
    A mesma partida aparece no battlelog de vários participantes."""
    tags = sorted(p["tag"] for t in item["battle"]["teams"] for p in t)
    return item["battleTime"] + "|" + ",".join(tags)


# ----------------------------------------------------------------------------
# Persistência (para retomar)
# ----------------------------------------------------------------------------
def carregar_estado():
    chaves = set()
    if ARQ_PARTIDAS.exists():
        with ARQ_PARTIDAS.open(encoding="utf-8") as f:
            for linha in f:
                try:
                    chaves.add(json.loads(linha)["_key"])
                except (json.JSONDecodeError, KeyError):
                    pass
    if ARQ_ESTADO.exists():
        est = json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))
        return deque(est["fila"]), set(est["visitados"]), set(est["enfileirados"]), chaves
    return None, set(), set(), chaves


def salvar_estado(fila, visitados, enfileirados):
    tmp = ARQ_ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "fila": list(fila),
        "visitados": list(visitados),
        "enfileirados": list(enfileirados),
    }), encoding="utf-8")
    tmp.replace(ARQ_ESTADO)  # escrita atômica


# ----------------------------------------------------------------------------
# Coleta principal
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Coleta partidas 3v3 do Brawl Stars (BFS).")
    ap.add_argument("--paises", nargs="+", default=["global", "BR", "US", "MX", "FR", "KR"],
                    help="Rankings usados como sementes")
    ap.add_argument("--max-jogadores", type=int, default=5000,
                    help="Quantos battlelogs baixar no total")
    ap.add_argument("--rps", type=float, default=10.0, help="Requisições por segundo")
    ap.add_argument("--checkpoint", type=int, default=50,
                    help="Salva o estado a cada N jogadores")
    args = ap.parse_args()

    if not TOKEN:
        sys.exit("Defina BRAWL_TOKEN no arquivo .env")

    DIR_RAW.mkdir(parents=True, exist_ok=True)
    cliente = ClienteBrawl(TOKEN, rps=args.rps)

    fila, visitados, enfileirados, chaves = carregar_estado()
    if fila is None:
        print("Buscando sementes nos rankings...")
        fila = deque()
        for pais in args.paises:
            for p in cliente.ranking_jogadores(pais):
                if p["tag"] not in enfileirados:
                    fila.append(p["tag"]); enfileirados.add(p["tag"])
            print(f"  {pais}: fila com {len(fila)} jogadores")
    else:
        print(f"Retomando: {len(visitados)} visitados, {len(fila)} na fila, "
              f"{len(chaves)} partidas já salvas")

    barra = tqdm(total=args.max_jogadores, initial=len(visitados), unit="jog")
    novas_total = 0
    try:
        with ARQ_PARTIDAS.open("a", encoding="utf-8") as saida:
            while fila and len(visitados) < args.max_jogadores:
                tag = fila.popleft()
                if tag in visitados:
                    continue
                visitados.add(tag)

                for item in cliente.battlelog(tag):
                    if not eh_3v3(item):
                        continue
                    # enfileira os outros jogadores (BFS)
                    for t in item["battle"]["teams"]:
                        for p in t:
                            if p["tag"] not in enfileirados:
                                fila.append(p["tag"]); enfileirados.add(p["tag"])
                    # salva se for partida nova
                    k = chave_partida(item)
                    if k in chaves:
                        continue
                    chaves.add(k)
                    item["_owner"] = tag   # o "result" é do ponto de vista dele
                    item["_key"] = k
                    saida.write(json.dumps(item, ensure_ascii=False) + "\n")
                    novas_total += 1

                barra.update(1)
                barra.set_postfix(partidas=len(chaves), fila=len(fila))
                if len(visitados) % args.checkpoint == 0:
                    saida.flush()
                    salvar_estado(fila, visitados, enfileirados)
    except KeyboardInterrupt:
        print("\nInterrompido — salvando estado...")
    finally:
        barra.close()
        salvar_estado(fila, visitados, enfileirados)
        print(f"Fim. Jogadores visitados: {len(visitados)} | "
              f"partidas únicas: {len(chaves)} (+{novas_total} nesta execução)")


if __name__ == "__main__":
    main()
