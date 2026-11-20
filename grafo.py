# Carrega o grafo de counters a partir dos CSVs gerados pelo processa.py
# Aresta A -> B significa que A vence B com frequencia significativa

import networkx as nx
import pandas as pd

PASTA = "data/processed/"


def carregar_counters(pesos=("small", "mid", "high")):
    brawlers = pd.read_csv(PASTA + "brawlers.csv")
    arestas = pd.read_csv(PASTA + "arestas.csv")

    G = nx.DiGraph()

    # so entram os brawlers que tiveram pelo menos um jogo
    for _, b in brawlers[brawlers["jogos"] > 0].iterrows():
        G.add_node(b["id"], nome=b["nome"].title(), jogos=b["jogos"],
                   taxa_vitoria=b["taxa_vitoria"])

    for _, a in arestas.iterrows():
        if a["peso"] in pesos:
            G.add_edge(a["origem"], a["destino"], taxa=a["taxa"], peso=a["peso"])

    return G


if __name__ == "__main__":
    G = carregar_counters()
    print(G.number_of_nodes(), "vertices e", G.number_of_edges(), "arestas")
