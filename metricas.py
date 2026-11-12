# Distribuicoes de metricas do grafo de counters
# Gera os graficos de grau e clustering na pasta figs/

import os

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

from grafo import carregar_counters

os.makedirs("figs", exist_ok=True)

G = carregar_counters()
H = G.to_undirected()  # versao nao dirigida, usada no grau total e no clustering

grau_entrada = [d for _, d in G.in_degree()]
grau_saida = [d for _, d in G.out_degree()]
grau_total = [d for _, d in H.degree()]


def ccdf(valores):
    # para cada valor x, fracao dos vertices com valor >= x
    valores = np.array(valores)
    x = np.unique(valores)
    y = [np.mean(valores >= v) for v in x]
    return x, y


# ---------- Figura 1: histograma dos graus ----------
fig, eixos = plt.subplots(1, 3, figsize=(15, 4))
dados = [(grau_entrada, "Grau de entrada"), (grau_saida, "Grau de saída"), (grau_total, "Grau total")]

for ax, (graus, titulo) in zip(eixos, dados):
    pesos = np.ones(len(graus)) / len(graus)  # eixo y como fracao dos vertices
    ax.hist(graus, bins=range(max(graus) + 2), weights=pesos, rwidth=0.9, align="left")
    ax.axvline(np.mean(graus), color="red", linestyle="--", label=f"média = {np.mean(graus):.1f}")
    ax.set_title(titulo)
    ax.set_xlabel("grau k")
    ax.set_ylabel("fração dos vértices")
    ax.legend()

plt.tight_layout()
plt.savefig("figs/fig01_grau.png", dpi=150)
plt.close()


# ---------- Figura 2: CCDF dos graus (log-log) ----------
plt.figure(figsize=(6.5, 4.5))
for graus, titulo in dados:
    x, y = ccdf([g for g in graus if g > 0])  # log de 0 nao existe
    plt.loglog(x, y, "o-", markersize=4, label=titulo)

plt.title("CCDF do grau")
plt.xlabel("grau k")
plt.ylabel("P(K ≥ k)")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("figs/fig02_ccdf_grau.png", dpi=150)
plt.close()


# ---------- Figura 3: clustering ----------
clustering = nx.clustering(H)
valores = list(clustering.values())

# clustering medio para cada grau, o C(k)
por_grau = {}
for v in H.nodes():
    k = H.degree(v)
    if k >= 2:  # com grau menor que 2 o clustering eh sempre 0
        por_grau.setdefault(k, []).append(clustering[v])
ks = sorted(por_grau)
c_medio = [np.mean(por_grau[k]) for k in ks]

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 4.3))

ax1.hist(valores, bins=20, range=(0, 1), weights=np.ones(len(valores)) / len(valores), rwidth=0.9)
ax1.axvline(np.mean(valores), color="red", linestyle="--", label=f"média = {np.mean(valores):.3f}")
ax1.set_title("Distribuição do clustering local")
ax1.set_xlabel("clustering local")
ax1.set_ylabel("fração dos vértices")
ax1.legend()

x, y = ccdf(valores)
ax2.plot(x, y, "o-", markersize=4)
ax2.set_title("CCDF do clustering local")
ax2.set_xlabel("clustering local c")
ax2.set_ylabel("P(C ≥ c)")

ax3.plot(ks, c_medio, "o-", markersize=4)
ax3.set_xscale("log")
ax3.set_yscale("log")
ax3.set_xticks([2, 5, 10, 20, 50], labels=["2", "5", "10", "20", "50"])
ax3.set_title("Clustering médio em função do grau, C(k)")
ax3.set_xlabel("grau k")
ax3.set_ylabel("C(k)")

for ax in (ax1, ax2, ax3):
    ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("figs/fig03_clustering.png", dpi=150)
plt.close()


print("Vertices:", G.number_of_nodes(), "| arestas:", G.number_of_edges())
print("Grau medio de entrada/saida:", round(np.mean(grau_saida), 2))
print("Grau maximo de entrada:", max(grau_entrada), "| de saida:", max(grau_saida))
print("Clustering medio:", round(np.mean(valores), 3))
print("Graficos salvos em figs/")
