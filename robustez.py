import random
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from grafo import carregar_counters

G = carregar_counters()
G.remove_nodes_from(list(nx.isolates(G)))   # tira os isolados 
N = G.number_of_nodes()
nome = nx.get_node_attributes(G, "nome")


#### ROBUSTEZ 
def maior_componente(H):
    if H.number_of_nodes() == 0:
        return 0
    return len(max(nx.weakly_connected_components(H), key=len)) / N

def curva(ordem):
    H = G.copy()
    componente_conforme_remocao = [maior_componente(G)] # começar com o normal
    for v in ordem:
        H.remove_node(v) #retira
        componente_conforme_remocao.append(maior_componente(H)) #adiciona novo
    return componente_conforme_remocao # vetor de componentes decaindo conforme remocao

# falha aleatória (média de 50 rodadas)
RODADAS = 50
todas_as_curvas = []

for semente in range(RODADAS):

    gerador = random.Random(semente)

    ordem = list(G.nodes())
    gerador.shuffle(ordem)

    curva_desta_rodada = curva(ordem)

    todas_as_curvas.append(curva_desta_rodada)


aleatoria = np.mean(todas_as_curvas, axis=0)

# ataque: ordenando pelo grau (maior pra menor)
ordem_ataque = sorted(G, key=G.degree, reverse=True)
ataque = curva(ordem_ataque)

x = np.arange(N + 1) / N
plt.plot(x, aleatoria, label="falha aleatória")
plt.plot(x, ataque, label="ataque por grau")
plt.xlabel("fração de vértices removidos"); plt.ylabel("maior componente / N")
plt.legend(); plt.grid(alpha=.3)
plt.savefig("figs/fig04_robustez.png", dpi=150); plt.close()

k = int(0.1 * N)
print("Após remover 10%: aleatória", round(aleatoria[k], 2), "| ataque", round(ataque[k], 2))
# RESULTADO: Após remover 10%: aleatória 0.9 | ataque 0.73


#### ALCANCE
alcance = {v: len(nx.descendants(G, v)) / (N - 1) for v in G}

# print(alcance)
# top 5 e base 5 por alcance
for v in sorted(alcance, key=alcance.get, reverse=True)[:5]:
    print(nome[v], f"alcança {alcance[v]:.0%}")
print("Alcançam ninguém:", sum(1 for a in alcance.values() if a == 0), "vértices")

# em quantos passos o maior hub alcança os demais
hub = max(G, key=G.out_degree)
dist = nx.single_source_shortest_path_length(G, hub)
print(nome[hub], "alcança", len(dist) - 1, "vértices; passos:", np.bincount(list(dist.values()))[1:])

plt.hist(list(alcance.values()), bins=20)
plt.xlabel("fração de vértices alcançáveis"); plt.ylabel("nº de brawlers")
plt.savefig("figs/fig05_difusao.png", dpi=150); plt.close()
# Mr. P alcança 76% # tá no meta
# Bibi alcança 66%
# Hank alcança 66% !interessante, apesar do boneco ser uma merda, por conta de um brawler ou outro ele acaba alcançando muita gente
# Mico alcança 65%
# Bo alcança 64%
# Alcançam ninguém: 32 vértices
# Mr. P alcança 74 vértices; passos: [62 11  1] # 62 em 1 passo, 11 em 2 passos, 1 em 3 passos


##### Clusterização para preservar info
U = G.to_undirected()
print("Clustering global (média local):", round(nx.average_clustering(U), 3))
print("Transitividade:", round(nx.transitivity(U), 3))
p = nx.density(U)
print("Densidade p (clustering esperado de uma ER):", round(p, 3))

# eficiência global ao remover os k mais centrais
base = nx.global_efficiency(U)
for k in [0, 1, 3, 5, 10]:
    H = U.copy(); H.remove_nodes_from(ordem_ataque[:k])
    print(f"remove {k:2d} hubs → eficiência {nx.global_efficiency(H) / base:.0%} da original")
# Clustering global (média local): 0.379
# Transitividade: 0.236
# Densidade p (clustering esperado de uma ER): 0.105
# remove  0 hubs → eficiência 100% da original
# remove  1 hubs → eficiência 93% da original
# remove  3 hubs → eficiência 83% da original
# remove  5 hubs → eficiência 71% da original
# remove 10 hubs → eficiência 47% da original


##### NAVEGAÇÃO
U = G.to_undirected()
maior = U.subgraph(max(nx.connected_components(U), key=len))
print("Caminho médio (não dirigido):", round(nx.average_shortest_path_length(maior), 2))
print("Diâmetro:", nx.diameter(maior))

# sentido dirigido: quantos pares (a, b) têm caminho a → b
pares = sum(len(nx.descendants(G, v)) for v in G)
print(f"Pares alcançáveis no sentido dirigido: {pares / (N * (N - 1)):.0%}")

d = [l for _, ds in nx.all_pairs_shortest_path_length(maior) for l in ds.values() if l > 0]
plt.hist(d, bins=range(1, max(d) + 2), align="left", rwidth=.9)
plt.xlabel("distância (passos)"); plt.ylabel("nº de pares")
plt.savefig("figs/fig06_navegacao.png", dpi=150); plt.close()
# Caminho médio (não dirigido): 2.16
# Diâmetro: 4
# Pares alcançáveis no sentido dirigido: 13%

# ranking de brawlers que mais counteram:


# DADOS DE CENTRALIDADE
vertices = G.nodes()
vertices_ordenados_out = sorted(vertices, key=G.out_degree, reverse=True)
vertices_ordenados_in = sorted(vertices, key=G.in_degree, reverse=True)
print("")
print("")


print("Lista de Brawlers que mais ganham (maior grau de saída):")
for v in vertices_ordenados_out:
    print(f"  {nome[v]}: {G.out_degree(v)} counterados")

print("")
print("")

print("Lista de Brawlers que mais perdem (maior grau de entrada):")
for v in vertices_ordenados_in:
    print(f"  {nome[v]}: {G.in_degree(v)} counterados")

print("")
print("")

U = G.to_undirected()

closeness   = nx.closeness_centrality(U)     # 
betweenness = nx.betweenness_centrality(U)   # 



print("Maiores closeness:")
for v in sorted(closeness, key=closeness.get, reverse=True)[:5]:
    print(nome[v], round(closeness[v], 3))
print("")


print("Maiores betweenness:")
for v in sorted(betweenness, key=betweenness.get, reverse=True)[:5]:
    print(nome[v], round(betweenness[v], 3))


# candidatos de melhor vértice: Mr. P (com certeza), Bo,  Edgar
# squeak e shade também são bem centrais, mas perdem bastante