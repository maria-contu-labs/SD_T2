#!/usr/bin/env python3
"""Gera graficos de E1 e E2/E4 a partir dos CSVs consolidados."""
import csv
from pathlib import Path
import matplotlib.pyplot as plt

PASTA = Path('resultados')
SAIDA = Path('docs/figuras')
SAIDA.mkdir(parents=True, exist_ok=True)


def linhas(arquivo):
    with (PASTA / arquivo).open(newline='') as f:
        return list(csv.DictReader(f))


def grafico_e1():
    dados = linhas('e1_mediana.csv')
    plt.figure(figsize=(9, 5.5))
    for sistema in ('etcd', 'cassandra'):
        rows = sorted((r for r in dados if r['sistema'] == sistema), key=lambda r: int(r['N']))
        x = [float(r['mediana_vazao_req_s']) for r in rows]
        y = [float(r['mediana_p99_ms']) for r in rows]
        plt.plot(x, y, marker='o', label=sistema)
        for r, a, b in zip(rows, x, y):
            plt.annotate('N=' + r['N'], (a, b), xytext=(4, 5), textcoords='offset points', fontsize=7)
    plt.yscale('log')
    plt.xlabel('Vazão efetiva (req/s)')
    plt.ylabel('Latência p99 (ms)')
    plt.title('E1: saturação')
    plt.grid(alpha=.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(SAIDA / 'e1_curva.png', dpi=160)
    plt.close()


def grafico_comparacao():
    dados = linhas('e2_e4_n2.csv')
    for op in ('GET', 'PUT'):
        plt.figure(figsize=(8, 5))
        for sistema in ('etcd', 'cassandra'):
            for e in ('E2', 'E4'):
                r = next(r for r in dados if r['sistema'] == sistema and r['experimento'] == e and r['operacao'] == op)
                plt.plot(['p50', 'p95', 'p99'], [float(r[c]) for c in ('p50_ms', 'p95_ms', 'p99_ms')], marker='o', label=f'{sistema} — {e}')
        plt.yscale('log')
        plt.ylabel('Latência (ms)')
        plt.title(f'E2 × E4: {op} (N=2)')
        plt.grid(alpha=.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(SAIDA / f'e2_e4_{op.lower()}.png', dpi=160)
        plt.close()


if __name__ == '__main__':
    grafico_e1()
    grafico_comparacao()
    print('Gráficos salvos em docs/figuras/')
