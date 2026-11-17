#!/usr/bin/env python3
"""Resume a medicao PILOTO do E2 a partir dos CSVs gravados pelos geradores."""
import csv
import gzip
import math
import sys
from collections import defaultdict
from pathlib import Path


def percentil(valores, p):
    return valores[math.ceil(p * len(valores)) - 1]


def main():
    if len(sys.argv) != 4:
        raise SystemExit("Uso: python3 scripts/resumo_piloto.py cassandra 2 99")
    sistema, n, repeticao = sys.argv[1:]
    base = Path("gerador/resultados/PILOTO")
    arquivos = sorted(base.glob(f"{sistema}_n{n}_r{repeticao}_p*.csv.gz"))
    if not arquivos:
        raise SystemExit("Nenhum CSV encontrado para essa execucao")

    latencias = defaultdict(list)
    erros = defaultdict(int)
    inicio, fim = float("inf"), 0.0
    for arquivo in arquivos:
        with gzip.open(arquivo, "rt", newline="") as f:
            for linha in csv.DictReader(f):
                inicio = min(inicio, float(linha["inicio_epoch"]))
                fim = max(fim, float(linha["fim_epoch"]))
                op = linha["op"]
                if linha["ok"] == "1":
                    latencias[op].append(float(linha["latencia_ms"]))
                else:
                    erros[op] += 1
    duracao = fim - inicio
    if duracao <= 0:
        raise SystemExit("Duracao invalida nos registros")
    print(f"\n{sistema} — {duracao:.1f} s, N={n}")
    for op in ("GET", "PUT"):
        valores = sorted(latencias[op])
        if not valores:
            print(f"{op}: sem sucessos ({erros[op]} erros)")
            continue
        print(
            f"{op}: {len(valores)} sucessos, {erros[op]} erros, "
            f"{len(valores) / duracao:.1f} req/s, "
            f"p50={percentil(valores, .50):.3f} ms, "
            f"p95={percentil(valores, .95):.3f} ms, "
            f"p99={percentil(valores, .99):.3f} ms"
        )


if __name__ == "__main__":
    main()
