#!/usr/bin/env python3
"""Analisa E6_V2: 12 execucoes N=2, sem relancar experimentos.
Uso: python3 analise_e6_final.py --input gerador/resultados/E6_V2 --output graficos/e6_final
"""
import argparse
import csv
import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

SCENARIOS = {
    ('etcd', 'lider'): 'etcd_lider',
    ('etcd', 'seguidor'): 'etcd_seguidor',
    ('cassandra', 'coordenador_n1'): 'cassandra_coordenador_n1',
    ('cassandra', 'coordenador_n2'): 'cassandra_coordenador_n2',
}


def fnum(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return None


def is_ok(value):
    return str(value).strip().lower() in {'true', '1', 'sim', 'yes', 'ok'}


def read_events(path):
    with path.open(newline='') as fh:
        rows = list(csv.DictReader(fh))
    return {r['evento']: float(r['epoch']) for r in rows}


def read_run(manifest_path):
    m = json.loads(manifest_path.read_text())
    key = (m.get('system'), m.get('role'))
    if key not in SCENARIOS or m.get('N_total') != 2:
        return None
    events = read_events(manifest_path.parent / m['events'])
    required = ['no_morto', 'reinicio_solicitado']
    if any(k not in events for k in required):
        print('AVISO: faltam eventos:', manifest_path)
        return None
    killed, restarted = events['no_morto'], events['reinicio_solicitado']
    if restarted <= killed:
        raise ValueError('Evento de reinicio anterior a falha em ' + str(manifest_path))
    stats = defaultdict(Counter)
    bins = defaultdict(Counter)
    puts_during = []
    puts_after = []
    alive_node_puts = []
    dead_node_puts = []
    rows_count = 0
    unique_nodes = set()
    missing_cols = set()
    for file in m['files']:
        p = manifest_path.parent / file
        if not p.is_file():
            print('AVISO: arquivo ausente:', p)
            return None
        op = gzip.open if p.suffix == '.gz' else open
        with op(p, mode='rt', newline='') as fh:
            rd = csv.DictReader(fh)
            reqcols = {'fim_epoch', 'op', 'ok'}
            if not reqcols.issubset(rd.fieldnames or []):
                raise ValueError(f'Colunas esperadas {reqcols}; {p} possui {rd.fieldnames}')
            for r in rd:
                t = fnum(r.get('fim_epoch'))
                if t is None or not math.isfinite(t):
                    continue
                operation = str(r.get('op', '')).strip().upper()
                if operation not in ('GET', 'PUT'):
                    continue
                success = is_ok(r.get('ok'))
                node = str(r.get('no', '')).strip()
                if node:
                    unique_nodes.add(node)
                phase = 'antes' if t < killed else ('falha' if t < restarted else 'depois')
                k = f'{operation}_{"ok" if success else "erro"}'
                stats[phase][k] += 1
                stats['TOTAL'][k] += 1
                bins[math.floor(t-killed)][k] += 1
                rows_count += 1
                if success and operation == 'PUT' and t >= killed:
                    if t < restarted:
                        puts_during.append(t-killed)
                    else:
                        puts_after.append(t-killed)
                    if node == m.get('target'):
                        dead_node_puts.append(t-killed)
                    elif node:
                        alive_node_puts.append(t-killed)
    return {'manifest': manifest_path, 'm': m, 'scenario': SCENARIOS[key],
            'killed': killed, 'restarted': restarted, 'stats': stats,
            'bins': bins, 'first_put_during': min(puts_during) if puts_during else None,
            'first_put_after': min(puts_after) if puts_after else None,
            'first_put_survivor': min(alive_node_puts) if alive_node_puts else None,
            'first_put_target': min(dead_node_puts) if dead_node_puts else None,
            'nodes': ','.join(sorted(unique_nodes)), 'rows_count': rows_count}


def fmt_num(v, digits=3):
    return '' if v is None else f'{v:.{digits}f}'


def rate(st, kind):
    ok = st.get(kind+'_ok',0)
    err = st.get(kind+'_erro',0)
    return err/(ok+err)*100 if ok+err else None


def main():
    pa = argparse.ArgumentParser()
    pa.add_argument('--input', default='gerador/resultados/E6_V2')
    pa.add_argument('--output', default='graficos/e6_final')
    args=pa.parse_args()
    base, out = Path(args.input), Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    manifests = sorted(base.glob('20261117T*/*.manifest.json'))
    if not manifests:
        manifests = sorted(base.glob('**/*.manifest.json'))
    runs=[]
    for p in manifests:
        x=read_run(p)
        if x:
            runs.append(x)
    if not runs:
        raise SystemExit('ERRO: nenhum manifesto E6 N=2 com CSV valido encontrado')

    fields=['sistema','cenario','repeticao','alvo','lider_antes','amostras','nos_vistos',
            'falha_s','primeiro_PUT_ok_durante_falha_s','primeiro_PUT_ok_sobreviventes_s',
            'primeiro_PUT_ok_no_alvo_s','primeiro_PUT_ok_apos_reinicio_s',
            'antes_GET_ok','antes_GET_erro','antes_PUT_ok','antes_PUT_erro',
            'falha_GET_ok','falha_GET_erro','falha_PUT_ok','falha_PUT_erro',
            'depois_GET_ok','depois_GET_erro','depois_PUT_ok','depois_PUT_erro',
            'falha_taxa_erro_GET_pct','falha_taxa_erro_PUT_pct']
    with (out/'e6_por_repeticao.csv').open('w',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=fields)
        wr.writeheader()
        for x in runs:
            m,s=x['m'],x['stats']
            r={'sistema':m['system'],'cenario':m['role'],'repeticao':m['rep'],
               'alvo':m.get('target'),'lider_antes':m.get('leader_before'),
               'amostras':x['rows_count'],'nos_vistos':x['nodes'],
               'falha_s':fmt_num(x['restarted']-x['killed']),
               'primeiro_PUT_ok_durante_falha_s':fmt_num(x['first_put_during']),
               'primeiro_PUT_ok_sobreviventes_s':fmt_num(x['first_put_survivor']),
               'primeiro_PUT_ok_no_alvo_s':fmt_num(x['first_put_target']),
               'primeiro_PUT_ok_apos_reinicio_s':fmt_num(x['first_put_after']),
               'falha_taxa_erro_GET_pct':fmt_num(rate(s['falha'],'GET'),2),
               'falha_taxa_erro_PUT_pct':fmt_num(rate(s['falha'],'PUT'),2)}
            for phase in ('antes','falha','depois'):
                for op in ('GET','PUT'):
                    for status in ('ok','erro'):
                        name=f'{phase}_{op}_{status}'
                        r[name]=s[phase].get(f'{op}_{status}',0)
            wr.writerow(r)

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        has_plot=True
    except ImportError:
        has_plot=False
        print('AVISO: matplotlib nao instalado; serao gerados somente os CSVs')

    summary=[]
    for name in ('etcd_lider','etcd_seguidor','cassandra_coordenador_n1','cassandra_coordenador_n2'):
        group=sorted((x for x in runs if x['scenario']==name),key=lambda x:x['m']['rep'])
        if not group: continue
        print('\n===',name,':',len(group),'repeticoes ===')
        for x in group:
            s=x['stats']['falha']; first=x['first_put_during']
            print(' r%d  alvo=%s  duracao=%.2fs  primeiro_PUT_apos_morte=%s s  durante_falha PUT_ok=%d PUT_erro=%d GET_ok=%d GET_erro=%d  PUT_erros=%s%%'%(
                x['m']['rep'],x['m']['target'],x['restarted']-x['killed'],
                fmt_num(first),s.get('PUT_ok',0),s.get('PUT_erro',0),s.get('GET_ok',0),s.get('GET_erro',0),fmt_num(rate(s,'PUT'),2)))
        candidates=[x['first_put_during'] for x in group if x['first_put_during'] is not None]
        med=statistics.median(candidates) if candidates else None
        print(' Mediana do intervalo ate primeiro PUT concluido dentro da falha:',fmt_num(med),'s')
        print(' NOTA: isso nao comprova eleicao/convergencia; uma escrita por outro no pode ter sucesso primeiro.')
        summary.append({'cenario':name,'repeticoes':len(group),'mediana_primeiro_PUT_ok_s':fmt_num(med),
                        'execucoes_com_PUT_ok_durante_falha':len(candidates),
                        'observacao':'intervalo a primeira conclusao bem sucedida; nao equivale a tempo de eleicao'})
        sec_start=-46; sec_end=136
        with (out/f'{name}_por_segundo.csv').open('w',newline='') as f:
            w=csv.writer(f)
            w.writerow(['segundo_relativo_falha','mediana_GET_ok','mediana_PUT_ok','mediana_erros','repeticoes'])
            for second in range(sec_start,sec_end):
                get=statistics.median(x['bins'][second].get('GET_ok',0) for x in group)
                put=statistics.median(x['bins'][second].get('PUT_ok',0) for x in group)
                err=statistics.median(x['bins'][second].get('GET_erro',0)+x['bins'][second].get('PUT_erro',0) for x in group)
                w.writerow([second,get,put,err,len(group)])
        if has_plot:
            secs=list(range(sec_start,sec_end))
            get=[statistics.median(x['bins'][t].get('GET_ok',0) for x in group) for t in secs]
            put=[statistics.median(x['bins'][t].get('PUT_ok',0) for x in group) for t in secs]
            err=[statistics.median(x['bins'][t].get('GET_erro',0)+x['bins'][t].get('PUT_erro',0) for x in group) for t in secs]
            fig,ax=plt.subplots(figsize=(10.5,3.4))
            ax.plot(secs,get,label='GET sucesso / s',lw=1.4)
            ax.plot(secs,put,label='PUT sucesso / s',lw=1.4)
            ax.plot(secs,err,label='Erros / s',lw=1.4)
            ax.axvline(0,ls='--',alpha=.7,label='No morto')
            ax.axvline(statistics.median(x['restarted']-x['killed'] for x in group),ls=':',alpha=.8,label='Reinicio solicitado')
            ax.set(xlabel='Segundos relativos a morte do no',ylabel='Requisicoes por segundo',title=f'E6: {name} (mediana de {len(group)} repeticoes, N=2)')
            ax.legend(loc='upper right',fontsize=8,ncol=2)
            ax.grid(alpha=.2)
            fig.tight_layout()
            fig.savefig(out/f'{name}_timeline.png',dpi=160)
            plt.close(fig)
    with (out/'e6_resumo.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['cenario','repeticoes','mediana_primeiro_PUT_ok_s','execucoes_com_PUT_ok_durante_falha','observacao'])
        w.writeheader();w.writerows(summary)
    print('\nRESULTADO:',len(runs),'manifestos; arquivos em',out)
    print('Para compartilhar, cole no chat: cat',out/'e6_por_repeticao.csv', 'e cat',out/'e6_resumo.csv')

if __name__=='__main__':
    main()
