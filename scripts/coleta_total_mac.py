#!/usr/bin/env python3
"""Coleta automatica E1-E6 para o SD_T2 no macOS (Docker Desktop).

Prioriza E1/E2/E4/E5/E6 e deixa o E3 demorado por ultimo.
Preserva execucoes completas; nunca mistura resultados de hosts diferentes.
Uso: caffeinate -dimsu python3 -u scripts/coleta_total_mac.py
"""
import argparse
import csv
import gzip
import json
import math
import os
import re
import shutil
import socket
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
RESULTS = ROOT / 'gerador' / 'resultados'
CONTROL = ROOT / 'logs' / 'coleta_total_mac'
CONTROL.mkdir(parents=True, exist_ok=True)
STATE_FILE = CONTROL / 'estado.json'
SYSTEMS = ('etcd', 'cassandra')
POINTS = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
PROCS = int(os.environ.get('PROCESSOS', '2'))
DISK_MIN_GIB = float(os.environ.get('DISCO_MIN_GIB', '1.5'))
FAILURES = []
STATE = {}


def say(message):
    print(f'[{datetime.now().astimezone().isoformat(timespec="seconds")}] {message}', flush=True)


def cmd(parts, env=None, capture=False, check=True, timeout=None):
    say('$ ' + ' '.join(map(str, parts)))
    result = subprocess.run(parts, cwd=ROOT, env=env, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.STDOUT if capture else None,
                            timeout=timeout)
    if check and result.returncode:
        if capture:
            print((result.stdout or '')[-1800:], flush=True)
        raise RuntimeError(f'Comando falhou (status {result.returncode}): {" ".join(map(str, parts))}')
    return result.stdout if capture else result.returncode


def save_state():
    tmp = STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_FILE)


def mark(key):
    STATE[key] = datetime.now(timezone.utc).isoformat()
    save_state()


def disk_check():
    free = shutil.disk_usage(ROOT).free / 1024 ** 3
    say(f'Disco livre: {free:.2f} GiB (minimo de seguranca {DISK_MIN_GIB:.2f} GiB)')
    if free < DISK_MIN_GIB:
        raise RuntimeError('Disco quase cheio: coleta interrompida antes de nova medicao; nenhum arquivo apagado')


def valid_run(exp, system, n, rep, seconds, warmup):
    base = RESULTS / exp / f'{system}_n{n}_r{rep}'
    path = Path(str(base) + '.manifest.json')
    try:
        man = json.loads(path.read_text())
        if (man['sistema'], man['experimento'], man['N_total'], man['repeticao'],
            man['processos'], man['seconds'], man['warmup']) != (
            system, exp, n, rep, min(PROCS, n), seconds, warmup):
            return False
        total_threads = 0
        for i in range(man['processos']):
            f = Path(str(base) + f'_p{i}.csv.gz')
            meta = json.loads(Path(str(f) + '.json').read_text())
            if f.stat().st_size == 0 or meta['duration_seconds'] != seconds or meta['warmup_seconds'] != warmup:
                return False
            total_threads += int(meta['threads'])
        return total_threads == n
    except (OSError, ValueError, KeyError, TypeError):
        return False


def skip_run(exp, system, n, rep, secs, warm):
    if not valid_run(exp, system, n, rep, secs, warm):
        return False
    if exp == 'E1':
        return True  # Aceita E1 anterior no mesmo Mac, se parametros e arquivos conferem.
    return f'{exp}:{system}:{n}:{rep}' in STATE


def wait_cql(timeout=420):
    deadline = time.monotonic() + timeout
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        ok = True
        for node in ('n1', 'n2', 'n3'):
            try:
                proc = subprocess.run(['docker', 'exec', node, 'cqlsh', '-e',
                                       'SELECT release_version FROM system.local;'],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      timeout=35, check=False)
                ready = proc.returncode == 0
            except subprocess.TimeoutExpired:
                ready = False
            if not ready:
                ok = False
                break
        if ok:
            say(f'Cassandra: CQL pronto nos tres nos (tentativa {attempt})')
            return
        if attempt % 6 == 1:
            say(f'Cassandra ainda inicializando CQL (tentativa {attempt})')
        time.sleep(5)
    raise RuntimeError('Cassandra nao ficou pronto na porta 9042 em todos os nos')


def wait_driver(timeout=360):
    snippet = ("from clientes import create_adapter, NODES; "
               "a=create_adapter('cassandra', 2.0); "
               "[a.execute(n, 'GET', b'k00000') for n in NODES]; a.close()")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            proc = subprocess.run(['docker', 'exec', 'gerador', 'python', '-c', snippet],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  timeout=40, check=False)
            if proc.returncode == 0:
                say('Driver do gerador confirmou os tres coordenadores CQL')
                return
        except subprocess.TimeoutExpired:
            pass
        time.sleep(5)
    raise RuntimeError('O gerador nao consegue acessar os tres coordenadores Cassandra')


def start_cluster(system):
    disk_check()
    say(f'== Reiniciando cluster {system} (sem tocar nos CSVs do host) ==')
    for s in SYSTEMS:
        cmd(['docker', 'compose', '-f', f'{s}.yml', 'down', '-v'], check=False)
    cmd(['bash', 'scripts/ambiente.sh', system])
    if system == 'cassandra':
        wait_cql()
    cmd(['bash', 'scripts/preparar.sh', system])
    if system == 'cassandra':
        wait_driver()


def stop_clusters():
    for s in SYSTEMS:
        cmd(['docker', 'compose', '-f', f'{s}.yml', 'down', '-v'], check=False)


def run_load(exp, system, n, rep):
    disk_check()
    seconds, warm = {'E1': (120, 30), 'E2': (180, 0), 'E4': (180, 30)}[exp]
    if skip_run(exp, system, n, rep, seconds, warm):
        say(f'PULANDO medicao valida: {exp} {system} N={n} r={rep}')
        return
    env = os.environ.copy()
    env.update(PROCESSOS=str(PROCS), DURACAO=str(seconds), WARMUP=str(warm), MONITORAR='1')
    say(f'INICIO {exp} {system} N={n} r={rep}')
    cmd(['bash', 'scripts/rodar_carga.sh', system, exp, str(n), str(rep)], env=env)
    if not valid_run(exp, system, n, rep, seconds, warm):
        raise RuntimeError(f'Arquivos incompletos para {exp} {system} N={n} r={rep}')
    mark(f'{exp}:{system}:{n}:{rep}')
    say(f'CONCLUIDO {exp} {system} N={n} r={rep}')


def choose_n(system):
    """Razao mediana throughput/p99, conforme criterio do analisar.py.

    Calcula p99 em histograma logaritmico (~2% por bucket), para nao
    manter milhoes de latencias na RAM do Mac.
    """
    runs = {}
    for n in POINTS:
        if not all(valid_run('E1', system, n, rep, 120, 30) for rep in (1, 2, 3)):
            say(f'E1 {system} N={n}: ponto incompleto; nao usado no calculo do N otimo')
            continue
        values = []
        for rep in (1, 2, 3):
            if not valid_run('E1', system, n, rep, 120, 30):
                raise RuntimeError(f'E1 incompleto: {system} N={n} r={rep}')
            base = RESULTS / 'E1' / f'{system}_n{n}_r{rep}'
            man = json.loads(Path(str(base) + '.manifest.json').read_text())
            metas = []
            files = []
            for i in range(man['processos']):
                p = Path(str(base) + f'_p{i}.csv.gz')
                files.append(p)
                metas.append(json.loads(Path(str(p) + '.json').read_text()))
            begin = max(m['started_epoch'] + m['warmup_seconds'] for m in metas)
            end = min(m['started_epoch'] + m['duration_seconds'] for m in metas)
            if end <= begin:
                raise RuntimeError('Processos sem janela comum para medir vazao')
            hist = [0] * 900
            ok = 0
            for path in files:
                with gzip.open(path, 'rt', encoding='utf-8', newline='') as fh:
                    for row in csv.DictReader(fh):
                        if row['fase'] != 'medicao' or row['ok'] != '1':
                            continue
                        if float(row['inicio_epoch']) < begin or float(row['fim_epoch']) > end:
                            continue
                        lat = max(0.01, float(row['latencia_ms']))
                        idx = max(0, min(len(hist)-1, int(math.log(lat / 0.01, 1.02))))
                        hist[idx] += 1
                        ok += 1
            if not ok:
                raise RuntimeError(f'E1 sem sucessos: {system} N={n} r={rep}')
            target = math.ceil(ok * 0.99)
            acc, p99 = 0, None
            for idx, count in enumerate(hist):
                acc += count
                if acc >= target:
                    p99 = 0.01 * 1.02 ** (idx + 1)
                    break
            values.append((ok / (end - begin), p99))
        throughput = statistics.median(v[0] for v in values)
        latency = statistics.median(v[1] for v in values)
        runs[n] = (throughput, latency, throughput / latency)
        say(f'E1 {system} N={n:3}: vazao_mediana={throughput:.1f} req/s; '
            f'p99_mediana~{latency:.3f} ms; razao={throughput/latency:.1f}')
    if len(runs) < 5:
        raise RuntimeError(f'Somente {len(runs)} pontos completos no E1; faltam dados para definir N')
    if len(runs) < len(POINTS):
        say(f'AVISO: E1 de {system} INCOMPLETO ({len(runs)}/10 pontos). N otimo PROVISORIO; '
            'os pontos ausentes continuam pendentes para o relatorio.')
    optimum = max(runs, key=lambda n: runs[n][2])
    report = CONTROL / f'n_otimo_{system}.csv'
    with report.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['sistema', 'N', 'vazao_mediana_req_s', 'p99_aproximado_ms', 'vazao_dividida_por_p99'])
        for n, data in runs.items():
            w.writerow([system, n, *[round(v, 5) for v in data]])
    override = os.environ.get('N_' + system.upper(), '')
    if override:
        override = int(override)
        if override not in POINTS:
            raise RuntimeError(f'N_{system.upper()} deve ser um dos pontos do E1')
        optimum = override
        say(f'N_otimo {system} FORCADO pelo usuario: {optimum}')
    say(f'N_otimo {system}: {optimum} (aprox. razao vazao/p99; confirmar joelho no grafico)')
    return optimum


def apply_latency():
    cmd(['bash', 'scripts/latencia_on.sh', '50ms', 'n1', 'n2', 'n3'])
    raw = cmd(['bash', 'scripts/rtt.sh', 'n1', '172.20.0.12'], capture=True)
    print(raw, flush=True)
    matches = re.findall(r'(?:rtt|round-trip) min/avg/max/(?:mdev|stddev)\s*=\s*[\d.]+/([\d.]+)/', raw)
    if not matches:
        raise RuntimeError('Nao consegui ler RTT real. Nao executar com atraso nao comprovado')
    avg = float(matches[-1])
    say(f'RTT inter-nos com netem: {avg:.2f} ms')
    if not (70 <= avg <= 200):
        raise RuntimeError(f'RTT inter-nos fora da faixa ~100ms: {avg:.1f}ms')


def remove_latency():
    cmd(['bash', 'scripts/latencia_off.sh', 'n1', 'n2', 'n3'], check=False)


def run_e1(system):
    missing = [(n, r) for n in POINTS for r in (1, 2, 3)
               if not skip_run('E1', system, n, r, 120, 30)]
    if not missing:
        say(f'E1 {system}: 30 manifestos validos; nenhuma repeticao necessaria')
        return
    say(f'E1 {system}: {len(missing)} repeticoes ausentes ou invalidas')
    start_cluster(system)
    for n, rep in missing:
        run_load('E1', system, n, rep)
    mark(f'E1:{system}:total')


def run_e2(system, n):
    missing = [r for r in (1, 2, 3) if not skip_run('E2', system, n, r, 180, 0)]
    if not missing:
        say(f'E2 {system}: 3 repeticoes validas nesta coleta')
        return
    start_cluster(system)
    for r in missing:
        run_load('E2', system, n, r)


def run_e4(system, n):
    missing = [r for r in (1, 2, 3) if not skip_run('E4', system, n, r, 180, 30)]
    if not missing:
        say(f'E4 {system}: 3 repeticoes validas nesta coleta')
        return
    start_cluster(system)
    try:
        apply_latency()
        for r in missing:
            run_load('E4', system, n, r)
    finally:
        remove_latency()


def run_e5(system, n):
    missing = [r for r in (1, 2, 3) if f'E5:{system}:{n}:{r}' not in STATE]
    if not missing:
        say(f'E5 {system}: 3 repeticoes desta coleta registradas')
        return
    start_cluster(system)
    for rep in missing:
        disk_check()
        cmd(['python3', 'orquestrar.py', 'E5', system, str(n), '--rep', str(rep)])
        p = RESULTS / 'E5' / f'{system}_n{n}_r{rep}.csv.gz'
        if (not p.is_file() or p.stat().st_size == 0 or
            not Path(str(p) + '.json').exists() or
            not Path(str(p) + '.eventos.csv').exists()):
            raise RuntimeError(f'E5 {system} r{rep}: resultado incompleto')
        events = Path(str(p) + '.eventos.csv').read_text()
        if 'gerador_finalizado' not in events or 'particao_curada' not in events:
            raise RuntimeError(f'E5 {system} r{rep}: falha na restauracao da rede')
        mark(f'E5:{system}:{n}:{rep}')
        if system == 'cassandra':
            wait_driver()
    say('ATENCAO: E5 registra particao/cura, mas prova de convergencia de escritas durante a particao exige verificacao adicional.')


def run_e6(system, n):
    key = f'E6_V2:{system}:{n}'
    if key in STATE:
        say(f'E6_V2 {system}: ja concluido nesta coleta')
        return
    start_cluster(system)
    env = os.environ.copy()
    env.update(PROCESSOS=str(PROCS), REPETICOES='3', CQL_READY_TIMEOUT='420')
    disk_check()
    cmd(['bash', 'scripts/executar_e6_v2.sh', system, str(n)], env=env)
    mark(key)


def stale_valid(path, expected=10000):
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        pairs = 0
        with gzip.open(path, 'rt', newline='', encoding='utf-8') as fh:
            for row in csv.DictReader(fh):
                if row.get('put_ok') == '1' and row.get('get_ok') == '1':
                    pairs += 1
        return pairs == expected
    except (OSError, EOFError, ValueError):
        return False


def run_e3(system, condition):
    paths = [RESULTS / 'E3' / f'{system}_stale_{condition}_r{r}.csv.gz' for r in (1, 2, 3)]
    missing = [(r, p) for r, p in enumerate(paths, 1) if not stale_valid(p)]
    if not missing:
        say(f'E3 {system} {condition}: tres arquivos completos de 10.000 pares')
        return
    start_cluster(system)
    try:
        if condition == 'alta':
            apply_latency()
        for rep, path in missing:
            disk_check()
            say(f'INICIO E3 {system} {condition} r={rep}; 10.000 pares sequenciais')
            cmd(['docker', 'exec', 'gerador', 'python', '/app/stale.py', system,
                 '--pairs', '10000', '--output',
                 f'/app/resultados/E3/{path.name}'])
            if not stale_valid(path):
                raise RuntimeError(f'E3 {system} {condition} r{rep}: menos de 10.000 pares validos')
            mark(f'E3:{system}:{condition}:{rep}')
            say(f'CONCLUIDO E3 {system} {condition} r={rep}')
    finally:
        if condition == 'alta':
            remove_latency()


def preflight():
    if PROCS < 1:
        raise RuntimeError('PROCESSOS deve ser positivo')
    required = ('scripts/ambiente.sh', 'scripts/preparar.sh', 'scripts/rodar_carga.sh',
                'scripts/latencia_on.sh', 'scripts/latencia_off.sh', 'scripts/rtt.sh',
                'scripts/executar_e6_v2.sh', 'orquestrar.py', 'orquestrar_e6_v2.py',
                'analisar_e6_v2.py', 'scripts/verificar_prontidao_e6.py',
                'gerador/stale.py', 'cassandra.yml', 'etcd.yml')
    missing = [p for p in required if not (ROOT / p).is_file()]
    if missing:
        raise RuntimeError('Arquivos faltando na pasta do Mac: ' + ', '.join(missing))
    if 'uuid.uuid4' not in (ROOT / 'gerador/stale.py').read_text(encoding='utf-8'):
        raise RuntimeError('gerador/stale.py nao tem isolamento de chave por repeticao; aplique a correção do E3 antes')
    cmd(['docker', 'info'], capture=True)
    cmd(['docker', 'compose', 'version'])
    disk_check()
    try:
        mem = int(cmd(['docker', 'info', '--format', '{{.MemTotal}}'], capture=True).strip())
        say(f'RAM disponivel ao Docker: {mem / 1024**3:.2f} GiB')
        if mem / 1024**3 < 5:
            say('AVISO: Cassandra pode atingir o limite de memoria do Docker; monitorar OOM no log.')
    except (ValueError, RuntimeError):
        pass
    say(f'Host: {socket.gethostname()}, projeto: {ROOT}')


def backup_once():
    key = 'backup_inicial'
    if key in STATE:
        return
    existing = [str(RESULTS.relative_to(ROOT))] if RESULTS.is_dir() else []
    if existing:
        disk_check()
        path = CONTROL / f'backup_pre_coleta_{datetime.now().strftime("%Y%m%d_%H%M%S")}.tar.gz'
        cmd(['tar', '-czf', str(path), *existing])
        say(f'Backup dos resultados antigos: {path}')
    mark(key)


def main():
    ap = argparse.ArgumentParser(description='Coleta automatica no Mac: E1 E2 E4 E5 E6 E3')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--check', action='store_true',
                    help='Verifica dependencias, Docker e disco sem iniciar medições')
    ap.add_argument('--etapas', default='E1,E2,E4,E5,E6,E3')
    ap.add_argument('--sistemas', default='etcd,cassandra')
    args = ap.parse_args()
    stages = [s.strip().upper() for s in args.etapas.split(',')]
    systems = [s.strip() for s in args.sistemas.split(',')]
    if any(s not in ('E1', 'E2', 'E3', 'E4', 'E5', 'E6') for s in stages):
        ap.error('Etapas invalidas')
    if any(s not in SYSTEMS for s in systems):
        ap.error('Sistemas invalidos')
    say('Plano: E1 -> E2 -> E4 -> E5 -> E6 -> E3 original -> E3 alta')
    say(f'Execucao solicitada: {stages}; sistemas: {systems}; processos geradores: {PROCS}')
    if args.dry_run:
        return 0
    preflight()
    if args.check:
        say('CHECK OK: todos os arquivos e Docker disponíveis. Nenhum container alterado.')
        return 0
    lock = CONTROL / 'em_execucao.lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise RuntimeError(f'Ja existe uma coleta rodando ou lock antigo: {lock}')
    try:
        global STATE
        if STATE_FILE.is_file():
            STATE = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        if STATE.get('host') and STATE['host'] != socket.gethostname():
            raise RuntimeError('Estado pertence a outro computador. Nao misture resultados do Mac e Codespaces.')
        STATE['host'] = socket.gethostname()
        STATE.setdefault('started_utc', datetime.now(timezone.utc).isoformat())
        save_state()
        backup_once()
        nopt = {}
        if any(s in stages for s in ('E2', 'E4', 'E5', 'E6')) and 'E1' not in stages:
            say('E1 nao foi solicitado; so sera usado se existirem 30 manifestos validos por sistema.')
        if 'E1' in stages:
            for system in systems:
                try:
                    run_e1(system)
                except Exception as exc:
                    FAILURES.append(f'E1 {system}: {exc}')
                    say(f'FALHA E1 {system}: {exc}')
        for system in systems:
            if any(s in stages for s in ('E2', 'E4', 'E5', 'E6')):
                try:
                    nopt[system] = choose_n(system)
                except Exception as exc:
                    FAILURES.append(f'N_otimo {system}: {exc}')
                    say(f'FALHA N_otimo {system}: {exc}; pulando E2/E4/E5/E6 deste sistema')
        for stage, function in [('E2', run_e2), ('E4', run_e4),
                                ('E5', run_e5), ('E6', run_e6)]:
            if stage not in stages:
                continue
            for system in systems:
                if system not in nopt:
                    continue
                try:
                    say(f'===== {stage} {system} N_otimo={nopt[system]} =====')
                    function(system, nopt[system])
                except Exception as exc:
                    FAILURES.append(f'{stage} {system}: {exc}')
                    say(f'FALHA {stage} {system}: {exc}; prosseguindo para a proxima etapa')
        if 'E3' in stages:
            for condition in ('original', 'alta'):
                for system in systems:
                    try:
                        say(f'===== E3 {system} {condition} =====')
                        run_e3(system, condition)
                    except Exception as exc:
                        FAILURES.append(f'E3 {system} {condition}: {exc}')
                        say(f'FALHA E3 {system} {condition}: {exc}; prosseguindo')
        say('===== RESUMO FINAL =====')
        if FAILURES:
            for f in FAILURES:
                say('PENDENTE: ' + f)
            say('A coleta terminou com pendencias. Arquivos ja concluidos foram preservados.')
            return 1
        say('Etapas solicitadas concluídas. Conferir graficos, validação E5 e analisar resultados.')
        return 0
    finally:
        try:
            remove_latency()
        except Exception:
            pass
        try:
            stop_clusters()
        except Exception:
            pass
        lock.rmdir()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say('Interrompido; resultados e estado salvos. Execute novamente para retomar.')
        sys.exit(130)
    except Exception as exc:
        say(f'ERRO FATAL: {exc}')
        sys.exit(1)
