"""Analisa arquivos de medições reais. Roda no HOST (pip install matplotlib)."""
import argparse
import csv
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


def percentile(samples, fraction):
    if not samples:
        return None
    a = sorted(samples)
    k = (len(a)-1)*fraction
    low, high = math.floor(k), math.ceil(k)
    return a[low] + (a[high]-a[low])*(k-low)


def median(items):
    return percentile(items, 0.5)


def iter_csv(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8', newline='') as fh:
        yield from csv.DictReader(fh)


def get_summary(path):
    meta = json.loads(Path(str(path)+'.json').read_text(encoding='utf-8'))
    ok_count = Counter()
    err_count = Counter()
    lat = defaultdict(list)
    series = Counter()
    for row in iter_csv(path):
        if row['fase'] != 'medicao':
            continue
        target = row['no']
        sec = math.floor(float(row['fim_epoch']))
        status = 'sucesso' if row['ok'] == '1' else 'erro'
        series[(sec, row['op'], target, status)] += 1
        if row['ok'] == '1':
            ok_count[row['op']] += 1
            lat[row['op']].append(float(row['latencia_ms']))
        else:
            err_count[row['op']] += 1
    effective_time = meta['duration_seconds'] - meta['warmup_seconds']
    out = []
    for op in ['GET', 'PUT', 'ALL']:
        vals = (lat['GET'] + lat['PUT']) if op == 'ALL' else lat[op]
        success = sum(ok_count.values()) if op == 'ALL' else ok_count[op]
        errors = sum(err_count.values()) if op == 'ALL' else err_count[op]
        out.append({
            'arquivo': str(path), 'sistema': meta['sistema'], 'N': meta['threads'],
            'experimento': experiment_of(path), 'operacao': op,
            'sucessos': success, 'erros': errors, 'tempo_medicao_s': effective_time,
            'vazao_req_s': round(success / effective_time, 4),
            'taxa_erro': round(errors / (success+errors), 6) if success+errors else 0,
            'p50_ms': percentile(vals, .5), 'p95_ms': percentile(vals, .95),
            'p99_ms': percentile(vals, .99)
        })
    return out, series



# _p0/_p1 indicam processos da MESMA repeticao; não são repeticoes diferentes.
GROUPED_FILE = re.compile(r"^(etcd|cassandra)_n(\d+)_r(\d+)_p(\d+)\.csv\.gz$")


def aggregate_run(paths, manifest_path):
    """Calcula percentis reais reunindo amostras, nunca somando/mediando p99.

    Considera apenas a intersecao temporal das janelas medidas de todos os
    processos, evitando extrapolar vazao quando um inicia/termina antes.
    """
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    metas = [json.loads(Path(str(path) + '.json').read_text(encoding='utf-8')) for path in paths]
    assert len(paths) == manifest['processos'], 'Faltam processos desta repeticao'
    assert sum(int(m['threads']) for m in metas) == manifest['N_total'], 'N total inconsistente'
    assert all(m['sistema'] == manifest['sistema'] for m in metas)
    assert all(m['duration_seconds'] == manifest['seconds'] and
               m['warmup_seconds'] == manifest['warmup'] for m in metas)
    begin = max(float(m['started_epoch']) + float(m['warmup_seconds']) for m in metas)
    finish = min(float(m['started_epoch']) + float(m['duration_seconds']) for m in metas)
    seconds = finish - begin
    if seconds <= 0:
        raise ValueError('Processos sem intervalo comum de medicao')
    oks = Counter()
    errs = Counter()
    lat = defaultdict(list)
    for path in paths:
        for row in iter_csv(path):
            if row['fase'] != 'medicao':
                continue
            if float(row['inicio_epoch']) < begin or float(row['fim_epoch']) > finish:
                continue
            if row['ok'] == '1':
                oks[row['op']] += 1
                lat[row['op']].append(float(row['latencia_ms']))
            else:
                errs[row['op']] += 1
    out = []
    for op in ('GET', 'PUT', 'ALL'):
        vals = lat['GET'] + lat['PUT'] if op == 'ALL' else lat[op]
        successes = sum(oks.values()) if op == 'ALL' else oks[op]
        errors = sum(errs.values()) if op == 'ALL' else errs[op]
        out.append({
            'arquivo': str(manifest_path), 'sistema': manifest['sistema'],
            'N': manifest['N_total'], 'experimento': manifest['experimento'],
            'operacao': op, 'sucessos': successes, 'erros': errors,
            'tempo_medicao_s': round(seconds, 6),
            'vazao_req_s': round(successes / seconds, 4),
            'taxa_erro': round(errors / (successes + errors), 6) if successes + errors else 0,
            'p50_ms': percentile(vals, .5), 'p95_ms': percentile(vals, .95),
            'p99_ms': percentile(vals, .99),
        })
    return out


def experiment_of(path):
    if 'piloto' in [part.lower() for part in Path(path).parts]:
        return 'PILOTO'
    name = str(path).lower()
    for experiment in ('e1', 'e2', 'e3', 'e4', 'e5', 'e6'):
        if experiment in Path(name).stem or experiment in Path(name).parts:
            return experiment.upper()
    return 'OUTRO'


def write_csv(path, rows, headers=None):
    if not rows and not headers:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = headers or list(rows[0])
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def graph_e1(data, out):
    out.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print('Sem matplotlib: CSV produzido, mas gráficos não foram criados.')
        return
    groups = defaultdict(lambda: defaultdict(list))
    for row in data:
        if row['experimento'] == 'E1' and row['operacao'] == 'ALL':
            groups[row['sistema']][int(row['N'])].append(row)
    if not groups:
        return
    summary = []
    fig, ax = plt.subplots(figsize=(9, 6))
    for system, by_n in sorted(groups.items()):
        dots = []
        for n, trials in sorted(by_n.items()):
            throughput = median([float(x['vazao_req_s']) for x in trials])
            p99 = median([float(x['p99_ms']) for x in trials if x['p99_ms'] is not None])
            if p99 is None:
                continue
            ratio = throughput / p99 if p99 > 0 else 0
            dots.append((throughput, p99, n, ratio))
            if len(trials) < 3:
                print(f'AVISO: {system} N={n} tem apenas {len(trials)} repeticao(oes); E1 exige 3')
            summary.append({'sistema': system, 'N': n, 'repeticoes': len(trials),
                            'mediana_vazao_req_s': throughput, 'mediana_p99_ms': p99,
                            'razao_vazao_p99': ratio})
        if not dots:
            continue
        dots.sort(key=lambda x: x[0])
        ax.plot([d[0] for d in dots], [d[1] for d in dots], 'o-', label=system)
        for throughput, p99, n, ratio in dots:
            ax.annotate(str(n), (throughput, p99), xytext=(3, 3), textcoords='offset points', fontsize=8)
        best = max(dots, key=lambda d: d[3])
        print(f'{system}: N ótimo pela razão vazão/p99 = {best[2]}, razão={best[3]:.2f}. '
              'Verifique manualmente se há ao menos dois pontos no platô.')
    ax.set_yscale('log')
    ax.set_xlabel('Vazão efetiva (req/s, mediana das repetições)')
    ax.set_ylabel('Latência p99 (ms, escala log)')
    ax.set_title('E1: Saturação / joelho')
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(out / 'e1_curva.png', dpi=180)
    plt.close(fig)
    write_csv(out / 'e1_mediana.csv', summary)


def graph_baseline(data, out):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    groups = defaultdict(list)
    for row in data:
        if row['experimento'] in ('E2', 'E4') and row['operacao'] in ('GET', 'PUT'):
            groups[(row['sistema'], row['experimento'], row['operacao'])].append(row)
    medians = []
    for (system, exp, op), vals in sorted(groups.items()):
        medians.append({'sistema': system, 'experimento': exp, 'op': op,
                        'N': median([int(x['N']) for x in vals]),
                        'repeticoes': len(vals),
                        **{k: median([float(x[k]) for x in vals if x[k] is not None])
                           for k in ('p50_ms', 'p95_ms', 'p99_ms', 'vazao_req_s')}})
    write_csv(out / 'e2_e4_mediana.csv', medians)
    # Um gráfico por operação, com séries E2 e E4 separadas por sistema.
    for op in ('GET', 'PUT'):
        rows = [r for r in medians if r['op'] == op]
        if not rows:
            continue
        fig, ax = plt.subplots(figsize=(9, 5))
        for row in rows:
            ax.plot(['p50', 'p95', 'p99'], [row['p50_ms'], row['p95_ms'], row['p99_ms']],
                    'o-', label=f"{row['sistema']} {row['experimento']}")
        ax.set_title(f'E2 vs E4: latência de {op}')
        ax.set_ylabel('Latência (ms)')
        ax.grid(alpha=.2)
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / f'e2_e4_{op.lower()}.png', dpi=180)
        plt.close(fig)


def graph_timelines(all_series, out):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    for path, series in all_series.items():
        exp = experiment_of(path)
        if exp not in ('E5', 'E6'):
            continue
        seconds = sorted({sec for sec, op, node, status in series})
        if not seconds:
            continue
        start = seconds[0]
        fig, ax = plt.subplots(figsize=(11, 5))
        for node in ('n1', 'n2', 'n3'):
            for status in ('sucesso', 'erro'):
                ys = [sum(series.get((sec, op, node, status), 0) for op in ('GET', 'PUT'))
                      for sec in seconds]
                ax.plot([sec-start for sec in seconds], ys,
                        label=f'{node} {status}', alpha=.85)
        event_log = Path(str(path) + '.eventos.csv')
        if event_log.is_file():
            for ev in iter_csv(event_log):
                if ev['evento'] in ('particao_iniciada', 'particao_curada', 'no_morto', 'no_reiniciado'):
                    position = float(ev['epoch']) - start
                    ax.axvline(position, ls='--', color='gray', alpha=.7)
                    ax.text(position, ax.get_ylim()[1]*.9, ev['evento'], rotation=90,
                            va='top', ha='right', fontsize=8)
        ax.set_title(f'{exp}: operações por segundo, {path.name}')
        ax.set_xlabel('Segundos desde a primeira completação registrada')
        ax.set_ylabel('Quantidade de completações')
        ax.legend(ncol=3)
        ax.grid(alpha=.2)
        fig.tight_layout()
        fig.savefig(out / f'{exp.lower()}_{path.name.replace(".csv.gz", "")}_timeline.png', dpi=180)
        plt.close(fig)


def stale_results(paths, out):
    results = []
    for path in paths:
        pairs = 0
        stale = 0
        errors = 0
        for row in iter_csv(path):
            if row['put_ok'] == '1' and row['get_ok'] == '1':
                pairs += 1
                stale += int(row['stale'])
            else:
                errors += 1
        results.append({'arquivo': str(path), 'sistema': path.name.split('_')[0],
                        'pares_validos': pairs, 'stale': stale, 'erros': errors,
                        'taxa_stale': stale / pairs if pairs else None})
    write_csv(out / 'e3_stale.csv', results)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='gerador/resultados')
    p.add_argument('--output', default='graficos')
    args = p.parse_args()
    root = Path(args.input)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    paths = sorted(root.rglob('*.csv.gz'))
    records = []
    consolidated = []
    timelines = {}
    stale_files = []
    grouped = defaultdict(list)
    for path in paths:
        if 'stale' in path.name or experiment_of(path) == 'E3':
            stale_files.append(path)
            continue
        if not Path(str(path)+'.json').is_file():
            print(f'Ignorando {path}, sem arquivo .json de metadados')
            continue
        rows, series = get_summary(path)
        records.extend(rows)
        timelines[path] = series
        match = GROUPED_FILE.fullmatch(path.name)
        if match and experiment_of(path) in ('PILOTO', 'E1', 'E2', 'E4'):
            group_key = (path.parent, match.group(1), int(match.group(2)), int(match.group(3)))
            grouped[group_key].append((int(match.group(4)), path))
        else:
            consolidated.extend(rows)
    for (folder, system, n, rep), pieces in sorted(grouped.items(), key=lambda x: str(x[0])):
        manifest_path = folder / f'{system}_n{n}_r{rep}.manifest.json'
        if not manifest_path.is_file():
            print(f'AVISO: {manifest_path} ausente; repeticao multiprocesso ignorada na comparacao')
            continue
        pieces.sort()
        expected_processes = json.loads(manifest_path.read_text(encoding='utf-8'))['processos']
        if [pid for pid, _ in pieces] != list(range(expected_processes)):
            print(f'AVISO: faltam arquivos de processos em {manifest_path}; ignorando')
            continue
        consolidated.extend(aggregate_run([path for _, path in pieces], manifest_path))
    write_csv(out / 'resumo_por_execucao.csv', records)
    write_csv(out / 'resumo_consolidado.csv', consolidated)
    graph_e1(consolidated, out)
    graph_baseline(consolidated, out)
    graph_timelines(timelines, out)
    if stale_files:
        stale_results(stale_files, out)
    print(f'{len(paths)} arquivos analisados em {out}')


if __name__ == '__main__':
    main()
