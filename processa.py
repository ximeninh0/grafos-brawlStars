"""
processa.py — Calcula quem é counter de quem a partir das partidas coletadas.

Decisões (e o motivo de cada uma):
  - Só partidas soloRanked: no tipo "ranked" (modo de troféus) os níveis dos
    brawlers variam de 1 a 11 e os donos dos logs vencem cerca de 62%.
  - Só partidas de mítico (os 6 jogadores com rank entre RANK_MIN e RANK_MAX):
    nos ranks baixos os donos dos logs vencem bem mais de 50%, e um único nível
    de jogo torna as vitórias mais comparáveis.
  - Empates e espelhos (mesmo brawler nos dois lados) ficam de fora.
  - Peso por série: jogos seguidos com os mesmos 6 jogadores não são independentes,
    então cada série soma peso total 1.
  - Taxa balanceada: média entre a vitória de A quando está no time do dono do log
    e quando está no time rival, o que neutraliza o viés de vitória dos donos.

Aresta A → B se:
  1. o par tem pelo menos MIN_JOGOS jogos e MIN_POR_LADO em cada lado;
  2. a taxa de A é significativa após a correção FDR (Benjamini–Hochberg);
  3. a taxa de A é de pelo menos 53% (small < 56% <= mid <= 60% < high).

Uso:
  python processa.py

Saídas (data/processed/):
  arestas.csv   counters: origem, destino, jogos, vitorias, taxa, n_efetivo, p_ajustado, peso
  pares.csv     todos os pares observados, inclusive os sem aresta
  brawlers.csv  id, nome, jogos, taxa_vitoria, taxa_escolha
"""

import collections
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from scipy.stats import false_discovery_control, norm

ARQUIVOS = [Path("data/raw/partidas.jsonl"), Path("data/piloto/partidas.jsonl"),
            Path("data/piloto_mitico/partidas.jsonl")]
ARQ_BRAWLERS = Path("brawlers.json")
DIR_SAIDA = Path("data/processed")

RANK_MIN, RANK_MAX = 13, 15  # supõe 13 a 15 = mítico; a API só informa o número
MIN_JOGOS = 50
MIN_POR_LADO = 10
ALFA = 0.05
MAX_INTERVALO_SERIE = 600  # segundos entre jogos da mesma série
TAXA_SMALL, TAXA_MID, TAXA_HIGH = 0.53, 0.56, 0.60


def na_faixa_de_rank(batalha: dict) -> bool:
    return all(RANK_MIN <= j["brawler"]["trophies"] <= RANK_MAX
               for time in batalha["teams"] for j in time)


def carregar_jogos() -> dict:
    """Agrupa os jogos soloRanked únicos, sem empate e na faixa de rank pelas 6 tags."""
    grupos = collections.defaultdict(list)
    chaves = set()
    for arquivo in ARQUIVOS:
        if not arquivo.exists():
            continue
        with arquivo.open(encoding="utf-8") as f:
            for linha in f:
                if '"soloRanked"' not in linha:  # evita decodificar o que será descartado
                    continue
                try:
                    partida = json.loads(linha)
                except json.JSONDecodeError:
                    continue  # linha cortada por uma interrupção
                batalha = partida["battle"]
                if batalha.get("type") != "soloRanked" or batalha.get("result") == "draw":
                    continue
                if not na_faixa_de_rank(batalha):
                    continue
                if partida["_key"] in chaves:
                    continue
                chaves.add(partida["_key"])

                t0, t1 = batalha["teams"]
                dono_em_t0 = partida["_owner"] in [j["tag"] for j in t0]
                time_dono, time_rival = (t0, t1) if dono_em_t0 else (t1, t0)
                tags = ",".join(sorted(j["tag"] for j in t0 + t1))
                grupos[tags].append((
                    partida["battleTime"],
                    [j["brawler"]["id"] for j in time_dono],
                    [j["brawler"]["id"] for j in time_rival],
                    batalha["result"] == "victory",
                ))
    return grupos


def _instante(battle_time: str) -> datetime:
    return datetime.strptime(battle_time[:15], "%Y%m%dT%H%M%S")


def separar_series(grupos: dict) -> list:
    """Quebra cada grupo de 6 jogadores em séries de jogos seguidos."""
    series = []
    for jogos in grupos.values():
        jogos.sort(key=lambda j: j[0])
        atual = [jogos[0]]
        for anterior, jogo in zip(jogos, jogos[1:]):
            if (_instante(jogo[0]) - _instante(anterior[0])).total_seconds() <= MAX_INTERVALO_SERIE:
                atual.append(jogo)
            else:
                series.append(atual)
                atual = [jogo]
        series.append(atual)
    return series


def novo_par() -> dict:
    return {"jogos_dono": 0, "jogos_rival": 0, "vitorias": 0,
            "peso_dono": 0.0, "peso_rival": 0.0, "vit_dono": 0.0, "vit_rival": 0.0}


def somar_par(pares: dict, a: int, b: int, a_venceu: bool, a_no_dono: bool, peso: float):
    if a > b:  # cada par é guardado uma vez, do ponto de vista do menor id
        a, b, a_venceu, a_no_dono = b, a, not a_venceu, not a_no_dono
    par = pares[(a, b)]
    lado = "dono" if a_no_dono else "rival"
    par[f"jogos_{lado}"] += 1
    par[f"peso_{lado}"] += peso
    par[f"vit_{lado}"] += peso * a_venceu
    par["vitorias"] += a_venceu


def contar(series: list):
    pares = collections.defaultdict(novo_par)
    brawlers = collections.defaultdict(novo_par)
    presenca = collections.Counter()
    for serie in series:
        peso = 1 / len(serie)
        for _, time_dono, time_rival, dono_venceu in serie:
            for a in time_dono:
                for b in time_rival:
                    if a != b:
                        somar_par(pares, a, b, dono_venceu, True, peso)
            for b_id, no_dono, venceu in (
                *((x, True, dono_venceu) for x in time_dono),
                *((x, False, not dono_venceu) for x in time_rival),
            ):
                lado = "dono" if no_dono else "rival"
                brawlers[b_id][f"jogos_{lado}"] += 1
                brawlers[b_id][f"peso_{lado}"] += peso
                brawlers[b_id][f"vit_{lado}"] += peso * venceu
            presenca.update(set(time_dono) | set(time_rival))
    return pares, brawlers, presenca


def taxa_balanceada(par: dict) -> float:
    """Média das taxas nos dois lados; NaN se um dos lados não tiver jogos."""
    if not par["peso_dono"] or not par["peso_rival"]:
        return math.nan
    return (par["vit_dono"] / par["peso_dono"] + par["vit_rival"] / par["peso_rival"]) / 2


def tabela_pares(pares: dict) -> pd.DataFrame:
    linhas = []
    for (a, b), par in pares.items():
        jogos = par["jogos_dono"] + par["jogos_rival"]
        taxa = taxa_balanceada(par)
        elegivel = (jogos >= MIN_JOGOS
                    and min(par["jogos_dono"], par["jogos_rival"]) >= MIN_POR_LADO)
        p_valor = math.nan
        if elegivel:
            # Erro padrão da média das duas taxas sob a hipótese de 50%.
            erro = 0.25 * math.sqrt(1 / par["peso_dono"] + 1 / par["peso_rival"])
            p_valor = 2 * norm.sf(abs(taxa - 0.5) / erro)
        linhas.append({
            "a": a, "b": b, "jogos": jogos, "vitorias_a": par["vitorias"], "taxa_a": taxa,
            "n_efetivo": par["peso_dono"] + par["peso_rival"], "p_valor": p_valor,
        })
    tabela = pd.DataFrame(linhas)
    testados = tabela["p_valor"].notna()
    tabela.loc[testados, "p_ajustado"] = false_discovery_control(
        tabela.loc[testados, "p_valor"], method="bh")
    return tabela.sort_values(["a", "b"], ignore_index=True)


def classificar(taxa: float) -> str:
    if taxa > TAXA_HIGH:
        return "high"
    return "mid" if taxa >= TAXA_MID else "small"


def tabela_arestas(pares: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for par in pares[pares["p_ajustado"] < ALFA].itertuples():
        a_vence = par.taxa_a > 0.5
        taxa = par.taxa_a if a_vence else 1 - par.taxa_a
        if taxa < TAXA_SMALL:
            continue
        linhas.append({
            "origem": par.a if a_vence else par.b,
            "destino": par.b if a_vence else par.a,
            "jogos": par.jogos,
            "vitorias": par.vitorias_a if a_vence else par.jogos - par.vitorias_a,
            "taxa": round(taxa, 4),
            "n_efetivo": round(par.n_efetivo, 1),
            "p_ajustado": par.p_ajustado,
            "peso": classificar(taxa),
        })
    return pd.DataFrame(linhas).sort_values("taxa", ascending=False, ignore_index=True)


def tabela_brawlers(brawlers: dict, presenca: collections.Counter, n_jogos: int) -> pd.DataFrame:
    linhas = []
    for b in json.loads(ARQ_BRAWLERS.read_text(encoding="utf-8")):
        dados = brawlers.get(b["id"], novo_par())
        linhas.append({
            "id": b["id"], "nome": b["name"],
            "jogos": dados["jogos_dono"] + dados["jogos_rival"],
            "taxa_vitoria": round(taxa_balanceada(dados), 4),
            "taxa_escolha": round(presenca[b["id"]] / n_jogos, 4),
        })
    return pd.DataFrame(linhas)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Lendo partidas soloRanked com os 6 jogadores entre os ranks {RANK_MIN} e {RANK_MAX}...")
    series = separar_series(carregar_jogos())
    n_jogos = sum(len(s) for s in series)

    pares_contados, brawlers_contados, presenca = contar(series)
    pares = tabela_pares(pares_contados)
    arestas = tabela_arestas(pares)
    brawlers = tabela_brawlers(brawlers_contados, presenca, n_jogos)

    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    arestas.to_csv(DIR_SAIDA / "arestas.csv", index=False)
    pares.to_csv(DIR_SAIDA / "pares.csv", index=False)
    brawlers.to_csv(DIR_SAIDA / "brawlers.csv", index=False)

    n_vertices = int((brawlers["jogos"] > 0).sum())
    possiveis = n_vertices * (n_vertices - 1) // 2
    print(f"Jogos: {n_jogos} | séries: {len(series)} | brawlers com jogos: {n_vertices}")
    print(f"Pares observados: {len(pares)} | testados: {pares['p_valor'].notna().sum()}")
    print(f"Arestas: {len(arestas)} ({100 * len(arestas) / possiveis:.1f}% dos pares possíveis)")
    print(arestas["peso"].value_counts().reindex(["high", "mid", "small"], fill_value=0).to_string())
    print(f"Arquivos salvos em {DIR_SAIDA}/")


if __name__ == "__main__":
    main()
