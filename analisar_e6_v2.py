"""Analisa exclusivamente runs E6_V2 completas a partir de seus manifestos.

Uso: python3 analisar_e6_v2.py --input gerador/resultados/E6_V2 --output graficos/e6_v2
"""
import argparse
import csv
import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as fh:
        yield from csv.DictReader(fh)


def percentile(samples, q):
    if not samples:
        return None
    ordered = sorted(samples)
    position = (len(ordered) - 1) * q
    lo, hi = math.floor(position), math.ceil(position)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo), 4)


def events_from(path):
    with path.open('r', encoding='utf-8', newline='') as fh:
        evs = list(csv.DictReader(fh))
    times = {row['evento']: float(row['epoch']) for row in evs}
    return times


def analyze_manifest(path):
    meta = json.loads(path.read_text(encoding='utf-8'))
    required = {'system', 'role', 'target', 'N_total', 'processes', 'files', 'events'}
    missing = required - set(meta)
    if missing:
        raise ValueError(f'{path}: faltam campos {missing}')
    files = [path.parent / filename for filename in meta['files']]
    if len(files) != meta['processes'] or not all(f.exists() and Path(str(f)+'.json').exists() for f in files):
        raise ValueError(f'{path}: arquivos de processos incompletos')
    metas = [json.loads(Path(str(f)+'.json').read_text(encoding='utf-8')) for f in files]
    if sum(int(m['threads']) for m in metas) != int(meta['N_total']):
        raise ValueError(f'{path}: número total de threads inconsistente')
    starts = [float(m['started_epoch']) for m in metas]
    begin = max(starts)
    end = min(float(m['finished_epoch']) for m in metas)
    if end <= begin:
        raise ValueError(f'{path}: janelas temporais não se sobrepõem')
    events = events_from(path.parent / meta['events'])
    if not {'no_morto', 'no_reiniciado'} <= events.keys():
        raise ValueError(f'{path}: eventos de falha/reinício ausentes')
    fault, restart = events['no_morto'], events['no_reiniciado']
    if not (begin < fault < restart < end):
        raise ValueError(f'{path}: timestamps fora da janela comum')

    count = Counter()
    per_second = Counter()
    latencies = defaultdict(list)
    put_success_after_fault = []
    put_target_recovered = []
    for file in files:
        for row in read_csv(file):
            if row['fase'] != 'medicao':
                continue
            start = float(row['inicio_epoch'])
            finish = float(row['fim_epoch'])
            if start < begin or finish > end:
                continue
            phase = 'antes' if start < fault else ('falha' if start < restart else 'recuperacao')
            node, op = row['no'], row['op']
            status = 'sucesso' if row['ok'] == '1' else 'erro'
            count[phase, node, op, status] += 1
            per_second[math.floor(finish), node, status] += 1
            if status == 'sucesso':
                latencies[phase, op].append(float(row['latencia_ms']))
                if op == 'PUT' and start >= fault and finish < restart and node != meta['target']:
                    put_success_after_fault.append(finish)
                if op == 'PUT' and start >= restart and node == meta['target']:
                    put_target_recovered.append(finish)

    count_all = Counter()
    for (phase, node, op, status), value in count.items():
        count_all[phase, status] += value
    summary = {
        'run': str(path), 'sistema': meta['system'], 'papel_alvo': meta['role'],
        'no_alvo': meta['target'], 'N_total': meta['N_total'], 'repeticao': meta['rep'],
        'processos': meta['processes'], 'janela_comum_s': round(end - begin, 3),
        'erros_total': sum(v for (_, _, _, status), v in count.items() if status == 'erro'),
        'sucessos_total': sum(v for (_, _, _, status), v in count.items() if status == 'sucesso'),
        'sucessos_falha': count_all['falha', 'sucesso'],
        'erros_falha': count_all['falha', 'erro'],
        # Proxy observacional. Não representa necessariamente election timeout puro.
        'primeiro_put_sucesso_outro_no_apos_falha_ms': (
            round((min(put_success_after_fault) - fault) * 1000, 3)
            if put_success_after_fault else None),
        'primeiro_put_sucesso_no_reiniciado_ms': (
            round((min(put_target_recovered) - restart) * 1000, 3)
            if put_target_recovered else None),
        'put_p99_ms_antes': percentile(latencies['antes', 'PUT'], .99),
        'put_p99_ms_falha': percentile(latencies['falha', 'PUT'], .99),
        'put_p99_ms_recuperacao': percentile(latencies['recuperacao', 'PUT'], .99),
    }
    per_node = []
    for phase in ('antes', 'falha', 'recuperacao'):
        for node in ('n1', 'n2', 'n3'):
            for op in ('GET', 'PUT'):
                per_node.append({'run': str(path), 'fase': phase, 'no': node, 'operacao': op,
                                 'sucessos': count[phase, node, op, 'sucesso'],
                                 'erros': count[phase, node, op, 'erro']})
    timeline = []
    for second in range(math.floor(begin), math.ceil(end) + 1):
        for node in ('n1', 'n2', 'n3'):
            timeline.append({'run': str(path), 'segundo_epoch': second, 'no': node,
                             'sucessos': per_second[second, node, 'sucesso'],
                             'erros': per_second[second, node, 'erro'],
                             'segundo_relativo': second - math.floor(begin),
                             'falha_rel_s': round(fault - begin, 3),
                             'reinicio_rel_s': round(restart - begin, 3)})
    return summary, per_node, timeline


def write_csv(path, rows):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def draw_timelines(output, manifests, rows):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print('matplotlib ausente: CSVs gerados, gráficos PNG opcionais')
        return
    by_run = defaultdict(list)
    for r in rows:
        by_run[r['run']].append(r)
    for manifest in manifests:
        data = by_run[str(manifest)]
        if not data:
            continue
        xs = sorted({row['segundo_relativo'] for row in data})
        fig, ax = plt.subplots(figsize=(11, 5))
        for node in ('n1', 'n2', 'n3'):
            for kind in ('sucessos', 'erros'):
                ys = [next(r[kind] for r in data if r['no'] == node and r['segundo_relativo'] == sec) for sec in xs]
                ax.plot(xs, ys, label=f'{node} {kind}', alpha=.8)
        first = data[0]
        ax.axvline(first['falha_rel_s'], color='gray', linestyle='--', label='nó morto')
        ax.axvline(first['reinicio_rel_s'], color='black', linestyle=':', label='nó reiniciado')
        ax.set(title=f'E6: {manifest.stem}', xlabel='Segundos desde início da janela comum',
               ylabel='Operações concluídas por segundo')
        ax.set_ylim(bottom=0)
        ax.legend(ncol=4, fontsize=8)
        ax.grid(alpha=.2)
        fig.tight_layout()
        fig.savefig(output / f'{manifest.stem}_timeline.png', dpi=150)
        plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='gerador/resultados/E6_V2')
    p.add_argument('--output', default='graficos/e6_v2')
    args = p.parse_args()
    manifests = sorted(Path(args.input).rglob('*.manifest.json'))
    if not manifests:
        raise SystemExit('Nenhum manifesto encontrado; E6_v2 ainda não foi executado')
    summaries, nodes, seconds = [], [], []
    for manifest in manifests:
        s, ns, ts = analyze_manifest(manifest)
        summaries.append(s)
        nodes.extend(ns)
        seconds.extend(ts)
    output = Path(args.output)
    write_csv(output / 'e6_v2_resumo.csv', summaries)
    write_csv(output / 'e6_v2_por_no.csv', nodes)
    write_csv(output / 'e6_v2_por_segundo.csv', seconds)
    draw_timelines(output, manifests, seconds)
    print(f'{len(manifests)} execuções analisadas em {output}')
    print('Atenção: primeiro PUT após falha mede recuperação observada, não tempo puro de eleição Raft.')


if __name__ == '__main__':
    main()
