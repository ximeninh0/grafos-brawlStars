"""
piloto_mitico.py — Mede quantas partidas novas de mítico rende quem já jogou nesse rank.

Sorteia jogadores que apareceram em partidas soloRanked de mítico nas coletas
anteriores e que ainda não tiveram o log baixado. Só lê as coletas anteriores;
tudo que gera fica em data/piloto_mitico/.

Uso:
  python piloto_mitico.py --n 3000

Para ampliar a coleta depois, rode com um --n maior. Os jogadores já baixados
são mantidos. Para retomar depois de um Ctrl+C, rode o mesmo comando.
"""

import argparse
import json
import sys
from pathlib import Path

from coleta import ARQ_ESTADO, TOKEN, ClienteBrawl
from piloto import DIR_PILOTO, FEITOS, PARTIDAS, coletar, ler_partidas, sortear
from processa import na_faixa_de_rank

DIR_MITICO = Path("data/piloto_mitico")
# Só as coletas anteriores: incluir a própria saída faria as partidas novas parecerem conhecidas.
COLETAS_ANTERIORES = [Path("data/raw") / PARTIDAS, DIR_PILOTO / PARTIDAS]

META_PARTIDAS = 140_000      # partidas novas para só mítico chegar perto de mítico ou acima
JOGADORES_POR_SEGUNDO = 2.9  # velocidade medida na última coleta


def eh_mitico(partida: dict) -> bool:
    """soloRanked sem empate e com os 6 jogadores na faixa de mítico."""
    batalha = partida["battle"]
    if batalha.get("type") != "soloRanked" or batalha.get("result") == "draw":
        return False
    return na_faixa_de_rank(batalha)


def mapear_coletas_anteriores():
    """Devolve as tags de quem jogou mítico e as chaves das partidas já coletadas."""
    tags, chaves = set(), set()
    for arquivo in COLETAS_ANTERIORES:
        with arquivo.open(encoding="utf-8") as f:
            for linha in f:
                if '"soloRanked"' not in linha:  # evita decodificar o que será descartado
                    continue
                try:
                    partida = json.loads(linha)
                except json.JSONDecodeError:
                    continue  # linha cortada por uma interrupção
                if eh_mitico(partida):
                    chaves.add(partida["_key"])
                    tags.update(j["tag"] for time in partida["battle"]["teams"] for j in time)
    return tags, chaves


def ja_baixados() -> set:
    visitados = set(json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))["visitados"])
    return visitados | set((DIR_PILOTO / FEITOS).read_text(encoding="utf-8").split())


def resumo(chaves_anteriores: set, n_candidatos: int):
    baixados = (DIR_MITICO / FEITOS).read_text(encoding="utf-8").split()
    novas = vitorias = 0
    for partida in ler_partidas(DIR_MITICO):
        if eh_mitico(partida) and partida["_key"] not in chaves_anteriores:
            novas += 1
            vitorias += partida["battle"]["result"] == "victory"

    print(f"\nJogadores baixados: {len(baixados)} | ainda disponíveis: {n_candidatos}")
    print(f"Partidas novas de mítico: {novas}")
    if not novas:
        return
    rendimento = novas / len(baixados)
    jogadores = META_PARTIDAS / rendimento
    horas = jogadores / JOGADORES_POR_SEGUNDO / 3600
    print(f"Partidas novas por jogador: {rendimento:.2f}")
    print(f"Vitória dos donos dos logs: {100 * vitorias / novas:.1f}%")
    print(f"Para {META_PARTIDAS} novas: ~{jogadores:.0f} jogadores, ~{horas:.1f} horas")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Piloto com jogadores já vistos em mítico.")
    ap.add_argument("--n", type=int, default=3000, help="Total de jogadores a baixar")
    ap.add_argument("--rps", type=float, default=10.0, help="Requisições por segundo")
    ap.add_argument("--semente", type=int, default=42, help="Semente do sorteio")
    args = ap.parse_args()

    if not TOKEN:
        sys.exit("Defina BRAWL_TOKEN no arquivo .env")

    DIR_MITICO.mkdir(parents=True, exist_ok=True)
    print("Lendo as coletas anteriores...")
    tags_mitico, chaves = mapear_coletas_anteriores()
    candidatos = sorted(tags_mitico - ja_baixados())

    tags = sortear(args.n, args.semente, DIR_MITICO, lambda: candidatos)
    try:
        coletar(ClienteBrawl(TOKEN, rps=args.rps), tags, DIR_MITICO)
    except KeyboardInterrupt:
        print("\nInterrompido. Rode o mesmo comando para continuar.")
    resumo(chaves, len(set(candidatos) - set(tags)))


if __name__ == "__main__":
    main()
