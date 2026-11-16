#!/usr/bin/env python3
"""Espera operacoes CQL reais nos 3 coordenadores antes do E6 Cassandra.

Executar no host que roda o Docker, dentro da raiz do projeto.
Nao altera chaves, containers ou politicas de replicacao.
"""
import argparse
import subprocess
import sys
import time

CHECK = """from clientes import create_adapter, NODES
adapter = create_adapter('cassandra', 2.0)
try:
    for node in NODES:
        adapter.execute(node, 'GET', b'k00000')
    print('Tres coordenadores CQL respondendo GET com CL=ONE', flush=True)
finally:
    adapter.close()
"""


def wait_ready(deadline_s, interval_s=4.0):
    deadline = time.monotonic() + deadline_s
    attempt = 0
    last_error = ''
    while time.monotonic() < deadline:
        attempt += 1
        remaining = deadline - time.monotonic()
        try:
            result = subprocess.run(
                ['docker', 'exec', 'gerador', 'python', '-c', CHECK],
                capture_output=True, text=True, timeout=max(1.0, min(40.0, remaining)),
            )
            if result.returncode == 0:
                print(f'Cassandra pronto para E6 ({attempt} tentativa(s)). {result.stdout.strip()}', flush=True)
                return True
            last_error = (result.stderr or result.stdout).strip()[-650:]
        except subprocess.TimeoutExpired:
            last_error = 'Timeout na consulta CQL dos tres coordenadores'
        except FileNotFoundError as exc:
            print(f'Docker indisponivel: {exc}', file=sys.stderr)
            return False
        print(f'Cassandra ainda nao pronto (tentativa {attempt}): {last_error}', file=sys.stderr, flush=True)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(interval_s, remaining))
    print(f'ERRO: Cassandra nao ficou pronto em {deadline_s}s. Ultimo erro: {last_error}', file=sys.stderr)
    return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()
    sys.exit(0 if wait_ready(args.timeout) else 1)
