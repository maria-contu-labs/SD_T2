"""Executa E5 ou E6, com injeção de falha na rede do cluster via Docker no HOST.

Uso: python orquestrar.py E5 etcd 16 --rep 1
     python orquestrar.py E6 etcd 16 --rep 1 --node n2
"""
import argparse
import csv
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def event(log, kind, extra=''):
    ts = time.time()
    with log.open('a', encoding='utf-8', newline='') as fh:
        writer = csv.writer(fh)
        if fh.tell() == 0:
            writer.writerow(['epoch', 'instante_utc', 'evento', 'detalhe'])
        writer.writerow([f'{ts:.6f}', datetime.fromtimestamp(ts, timezone.utc).isoformat(), kind, extra])
    print(f'{kind} ({extra}), UTC={datetime.fromtimestamp(ts, timezone.utc).isoformat()}', flush=True)


def call(*cmd):
    subprocess.run(cmd, check=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('experiment', choices=['E5', 'E6'])
    p.add_argument('system', choices=['etcd', 'cassandra'])
    p.add_argument('N', type=int)
    p.add_argument('--rep', type=int, default=1)
    p.add_argument('--node', choices=['n1', 'n2', 'n3'], default='n1',
                   help='E6: identificar previamente lider ou seguidor de etcd')
    p.add_argument('--before', type=int, default=45)
    p.add_argument('--fault-seconds', type=int, default=60)
    p.add_argument('--after', type=int, default=75)
    args = p.parse_args()
    if min(args.N, args.rep, args.before, args.fault_seconds, args.after) <= 0:
        p.error('N, rep e durações devem ser positivos')
    output = Path('gerador/resultados') / args.experiment / f'{args.system}_n{args.N}_r{args.rep}.csv.gz'
    output.parent.mkdir(parents=True, exist_ok=True)
    log = Path(str(output) + '.eventos.csv')
    log.unlink(missing_ok=True)
    duration = args.before + args.fault_seconds + args.after + 10
    command = ['docker', 'exec', 'gerador', 'python', '/app/carga.py', args.system,
               '--threads', str(args.N), '--seconds', str(duration), '--warmup', '0',
               '--seed', '2026', '--output', '/app/resultados/' +
               str(output.relative_to(Path('gerador/resultados')))]
    print('Iniciando:', ' '.join(command), flush=True)
    process = subprocess.Popen(command)
    fault_done = False
    event(log, 'gerador_iniciado', '')
    try:
        time.sleep(args.before)
        if args.experiment == 'E5':
            event(log, 'particao_iniciada', 'n1 separado de n2,n3')
            call('docker', 'network', 'disconnect', 'lab_cluster', 'n1')
        else:
            event(log, 'no_morto', args.node)
            call('docker', 'kill', args.node)
        fault_done = True
        time.sleep(args.fault_seconds)
        if args.experiment == 'E5':
            event(log, 'particao_curada', 'n1 reconectado com IP 172.20.0.11')
            call('docker', 'network', 'connect', '--ip', '172.20.0.11', 'lab_cluster', 'n1')
        else:
            event(log, 'no_reiniciado', args.node)
            call('docker', 'start', args.node)
        fault_done = False
        process.wait(timeout=args.after + 60)
        if process.returncode != 0:
            raise RuntimeError(f'Gerador terminou com código {process.returncode}')
        event(log, 'gerador_finalizado', '')
    finally:
        if fault_done:
            print('Tentando restaurar conectividade do cluster...', flush=True)
            if args.experiment == 'E5':
                subprocess.run(['docker', 'network', 'connect', '--ip', '172.20.0.11',
                                'lab_cluster', 'n1'], check=False)
            else:
                subprocess.run(['docker', 'start', args.node], check=False)
        if process.poll() is None:
            process.terminate()
            process.wait()
    print(f'Amostras: {output}; eventos: {log}')


if __name__ == '__main__':
    main()
