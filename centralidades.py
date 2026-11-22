

from collections import Counter

import networkx as nx

from grafo import carregar_counters


def main():
    grafo = carregar_counters()
    nomes = nx.get_node_attributes(grafo, "nome")
    grau_saida = dict(grafo.out_degree())


    metricas = {
        "Grau de entrada": dict(grafo.in_degree()),
        "Grau de saída": grau_saida,
        "Betweenness": nx.betweenness_centrality(grafo),
        "Closeness de saída": nx.closeness_centrality(
            grafo.reverse(copy=False), wf_improved=True
        ),
    }
    rankings = [
        sorted(valores, key=lambda v: (-valores[v], nomes[v], v))[:5]
        for valores in metricas.values()
    ]
    aparicoes = Counter(vertice for ranking in rankings for vertice in ranking)

    print(f"Grafo com {grafo.number_of_nodes()} vértices e {grafo.number_of_edges()} arestas.\n")
    print("| Posição | " + " | ".join(metricas) + " |")
    print("| " + " | ".join(["---"] * (len(metricas) + 1)) + " |")
    for posicao, vertices in enumerate(zip(*rankings), start=1):
        celulas = []
        for vertice, valores in zip(vertices, metricas.values()):
            valor = valores[vertice]
            texto = f"{valor:.6f}".replace(".", ",") if isinstance(valor, float) else str(valor)
            celulas.append(f"{nomes[vertice]} ({texto})")
        print(f"| {posicao} | " + " | ".join(celulas) + " |")

    classificacao = sorted(
        aparicoes, key=lambda v: (-aparicoes[v], -grau_saida[v], nomes[v], v)
    )
    print("\nClassificação por aparições no top 5, com desempate por grau de saída:")
    for posicao, vertice in enumerate(classificacao, start=1):
        print(
            f"{posicao}. {nomes[vertice]} ({aparicoes[vertice]} aparições, "
            f"grau de saída {grau_saida[vertice]})"
        )


if __name__ == "__main__":
    main()
