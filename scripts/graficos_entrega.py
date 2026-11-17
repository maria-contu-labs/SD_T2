import csv
from pathlib import Path

import matplotlib.pyplot as plt

figuras = Path("docs/figuras")
resultados = Path("resultados")
figuras.mkdir(parents=True, exist_ok=True)
resultados.mkdir(parents=True, exist_ok=True)


def ler_csv(caminho):
    with open(caminho, newline="") as arquivo:
        return list(csv.DictReader(arquivo))


# E1: p99 x vazao, com pontos ordenados por N.
e1 = ler_csv(resultados / "e1_mediana.csv")

plt.figure(figsize=(9, 5.5))

for sistema in ("etcd", "cassandra"):
    dados = sorted(
        (r for r in e1 if r["sistema"] == sistema),
        key=lambda r: int(r["N"])
    )

    vazao = [float(r["mediana_vazao_req_s"]) for r in dados]
    p99 = [float(r["mediana_p99_ms"]) for r in dados]

    plt.plot(vazao, p99, marker="o", label=sistema)

    for r, x, y in zip(dados, vazao, p99):
        plt.annotate(
            f"N={r['N']}",
            (x, y),
            xytext=(4, 5),
            textcoords="offset points",
            fontsize=7
        )

plt.yscale("log")
plt.xlabel("Vazao efetiva (req/s)")
plt.ylabel("Latencia p99 (ms) - escala log")
plt.title("E1 - Saturacao")
plt.grid(alpha=0.3)
plt.legend()
plt.tight_layout()
plt.savefig(figuras / "e1_curva.png", dpi=170)
plt.close()


# E2 e E4: dados consolidados das tres repeticoes com N=2.
resumo = []

for linha in ler_csv(resultados / "e2_e4_n2.csv"):
    for campo in ("p50_ms", "p95_ms", "p99_ms", "vazao_req_s"):
        linha[campo] = float(linha[campo])
    resumo.append(linha)

if len(resumo) != 8:
    raise ValueError("Resumo E2/E4 incompleto")

for operacao in ("GET", "PUT"):
    plt.figure(figsize=(8, 5))

    for sistema in ("etcd", "cassandra"):
        for experimento in ("E2", "E4"):
            linha = next(
                r for r in resumo
                if r["sistema"] == sistema
                and r["experimento"] == experimento
                and r["operacao"] == operacao
            )

            valores = [
                linha["p50_ms"],
                linha["p95_ms"],
                linha["p99_ms"]
            ]

            plt.plot(
                ["p50", "p95", "p99"],
                valores,
                marker="o",
                label=f"{sistema} - {experimento}"
            )

    plt.yscale("log")
    plt.ylabel("Latencia (ms) - escala log")
    plt.title(f"E2 x E4 - {operacao} (N=2)")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(
        figuras / f"e2_e4_{operacao.lower()}.png",
        dpi=170
    )
    plt.close()

print("Graficos gerados em docs/figuras/")
print("\nResumo E2/E4:")
for r in resumo:
    print(
        f"{r['sistema']:10} "
        f"{r['experimento']} "
        f"{r['operacao']:3} "
        f"p99={r['p99_ms']:.3f} ms "
        f"vazao={r['vazao_req_s']:.1f} req/s"
    )
