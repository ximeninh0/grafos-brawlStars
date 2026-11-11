"""
piloto.py — Testa se o viés de vitória dos donos dos logs vem de amostrar perto do topo.

Sorteia jogadores da fila que a coleta principal deixou em data/raw/estado.json,
baixa os battlelogs deles e compara a taxa de vitória com a da base principal.
Só lê data/raw/; tudo que gera fica em data/piloto/.

Uso:
  python piloto.py --n 3000

Para retomar depois de um Ctrl+C, rode o mesmo comando.
"""

import argparse
import collections
import json
import random
import sys
from pathlib import Path

from tqdm import tqdm

from coleta import ARQ_ESTADO, TOKEN, ClienteBrawl, chave_partida, eh_3v3

DIR_PILOTO = Path("data/piloto")
SORTEADOS = "sorteados.json"
FEITOS = "feitos.txt"
PARTIDAS = "partidas.jsonl"

# Taxa de vitória dos donos dos logs na base principal (30 mil jogadores).
BASE = {"ranked": 62.4, "soloRanked": 53.5, "todas": 59.4}


def fila_principal() -> list:
    if not ARQ_ESTADO.exists():
        sys.exit(f"{ARQ_ESTADO} não encontrado: rode a coleta principal antes.")
    return json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))["fila"]


def sortear(n: int, semente: int, pasta: Path, obter_candidatos) -> list:
    """Mantém os jogadores já sorteados e sorteia só os que faltam para chegar a n."""
    arquivo = pasta / SORTEADOS
    tags = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else []
    faltam = n - len(tags)
    if faltam <= 0:
        return tags
    ja_sorteados = set(tags)
    candidatos = [t for t in obter_candidatos() if t not in ja_sorteados]
    if faltam > len(candidatos):
        sys.exit(f"Só há {len(candidatos)} jogadores disponíveis (faltam: {faltam}).")
    tags += random.Random(semente + len(tags)).sample(candidatos, faltam)
    arquivo.write_text(json.dumps(tags), encoding="utf-8")
    return tags


def ler_partidas(pasta: Path):
    """Lê uma partida por vez, para não carregar o arquivo inteiro na memória."""
    arquivo = pasta / PARTIDAS
    if not arquivo.exists():
        return
    with arquivo.open(encoding="utf-8") as f:
        for linha in f:
            try:
                yield json.loads(linha)
            except json.JSONDecodeError:
                pass  # linha cortada por uma interrupção


def coletar(cliente, tags: list, pasta: Path):
    caminho_feitos = pasta / FEITOS
    feitos = set(caminho_feitos.read_text(encoding="utf-8").split()) if caminho_feitos.exists() else set()
    chaves = {p["_key"] for p in ler_partidas(pasta)}
    pendentes = [t for t in tags if t not in feitos]

    with (pasta / PARTIDAS).open("a", encoding="utf-8") as saida, \
            caminho_feitos.open("a", encoding="utf-8") as arq_feitos:
        for tag in tqdm(pendentes, total=len(tags), initial=len(tags) - len(pendentes), unit="jog"):
            for item in cliente.battlelog(tag):
                if not eh_3v3(item):
                    continue
                chave = chave_partida(item)
                if chave in chaves:
                    continue
                chaves.add(chave)
                item["_owner"] = tag
                item["_key"] = chave
                saida.write(json.dumps(item, ensure_ascii=False) + "\n")
            saida.flush()
            arq_feitos.write(tag + "\n")
            arq_feitos.flush()


def resumo():
    vitorias, jogos = collections.Counter(), collections.Counter()
    donos = set()
    for p in ler_partidas(DIR_PILOTO):
        donos.add(p["_owner"])
        resultado = p["battle"].get("result")
        if resultado not in ("victory", "defeat"):
            continue
        for grupo in (p["battle"].get("type"), "todas"):
            vitorias[grupo] += resultado == "victory"
            jogos[grupo] += 1

    print(f"\nJogadores com partidas 3v3: {len(donos)} | partidas sem empate: {jogos['todas']}")
    print(f"{'tipo':<12}{'partidas':>10}{'piloto':>10}{'base':>10}")
    for grupo in ("ranked", "soloRanked", "todas"):
        if jogos[grupo]:
            taxa = 100 * vitorias[grupo] / jogos[grupo]
            print(f"{grupo:<12}{jogos[grupo]:>10}{taxa:>9.1f}%{BASE[grupo]:>9.1f}%")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Piloto com jogadores sorteados da fila.")
    ap.add_argument("--n", type=int, default=3000, help="Quantos jogadores sortear")
    ap.add_argument("--rps", type=float, default=10.0, help="Requisições por segundo")
    ap.add_argument("--semente", type=int, default=42, help="Semente do sorteio")
    args = ap.parse_args()

    if not TOKEN:
        sys.exit("Defina BRAWL_TOKEN no arquivo .env")

    DIR_PILOTO.mkdir(parents=True, exist_ok=True)
    tags = sortear(args.n, args.semente, DIR_PILOTO, fila_principal)
    try:
        coletar(ClienteBrawl(TOKEN, rps=args.rps), tags, DIR_PILOTO)
    except KeyboardInterrupt:
        print("\nInterrompido. Rode o mesmo comando para continuar.")
    resumo()


if __name__ == "__main__":
    main()
