"""E6 auditável: duas variantes de falha e carga multiprocesso por N total.

Executar somente em ambiente Docker autorizado; não limpa volumes.
"""
import argparse
import csv
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

NODES = ("n1", "n2", "n3")
ENDPOINTS = "http://172.21.0.11:2379,http://172.21.0.12:2379,http://172.21.0.13:2379"


def run_command(*parts, timeout=30):
    return subprocess.run(parts, text=True, capture_output=True, check=True, timeout=timeout)


def etcd_leader():
    """Não presume que n1 seja o líder; falha sem confirmação inequívoca."""
    raw = run_command("docker", "exec", "n1", "etcdctl", f"--endpoints={ENDPOINTS}",
                      "endpoint", "status", "--cluster", "-w", "json").stdout
    data = json.loads(raw)
    leaders = set()
    for item in data:
        status = item.get("Status", item.get("status", {}))
        header = status.get("header", {})
        member = str(header.get("member_id", ""))
        leader = str(status.get("leader", ""))
        if member and leader and member == leader:
            match = re.search(r"172\.21\.0\.(1[1-3])(?::|/|$)", item.get("Endpoint", item.get("endpoint", "")))
            if match:
                leaders.add("n" + str(int(match.group(1)) - 10))
    if len(leaders) != 1:
        raise RuntimeError("Não foi possível determinar um líder Raft único; abortando E6")
    return leaders.pop()


def choose_target(system, role, leader=None):
    if system == "etcd":
        if role not in ("lider", "seguidor") or leader not in NODES:
            raise ValueError("Para etcd é obrigatório um líder confirmado")
        return leader if role == "lider" else next(n for n in NODES if n != leader)
    if role == "coordenador_n1":
        return "n1"
    if role == "coordenador_n2":
        return "n2"
    raise ValueError("Cassandra não possui líder/seguidor: usar coordenador_n1 ou coordenador_n2")


def log_event(path, kind, detail=""):
    epoch = time.time()
    empty = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if empty:
            writer.writerow(["epoch", "instante_utc", "evento", "detalhe"])
        writer.writerow([f"{epoch:.6f}", datetime.fromtimestamp(epoch, timezone.utc).isoformat(), kind, detail])
    print(f"{kind}: {detail} @ {epoch:.6f}", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("system", choices=("etcd", "cassandra"))
    p.add_argument("N", type=int)
    p.add_argument("--role", required=True)
    p.add_argument("--rep", type=int, default=1)
    p.add_argument("--processes", type=int, default=2)
    p.add_argument("--before", type=int, default=45)
    p.add_argument("--fault-seconds", type=int, default=60)
    p.add_argument("--after", type=int, default=75)
    p.add_argument("--folder", default="E6_V2")
    args = p.parse_args()
    if min(args.N, args.rep, args.processes, args.before, args.fault_seconds, args.after) < 1:
        p.error("N, rep, processos e durações devem ser positivos")
    if args.processes > args.N:
        p.error("Número de processos não pode exceder N")
    if not re.fullmatch(r"[A-Za-z0-9_/-]+", args.folder) or ".." in args.folder:
        p.error("Folder inválida")

    root = Path("gerador/resultados") / args.folder
    root.mkdir(parents=True, exist_ok=True)
    prefix = f"{args.system}_{args.role}_n{args.N}_r{args.rep}"
    manifest = root / f"{prefix}.manifest.json"
    events = root / f"{prefix}.eventos.csv"
    if manifest.exists() or events.exists() or list(root.glob(f"{prefix}_p*.csv.gz")):
        raise FileExistsError(f"Execução já existe: {prefix}; use outra pasta de resultados")

    files, procs, handles = [], [], []
    duration = args.before + args.fault_seconds + args.after
    fault_active = False
    target = None
    started_epoch = time.time()
    log_event(events, "inicio_orquestracao", f"{args.system}, role={args.role}, N={args.N}")
    try:
        for index in range(args.processes):
            threads = args.N // args.processes + (1 if index < args.N % args.processes else 0)
            seed = 2026 + args.rep * 10000019 + index * 1000003
            filename = f"{prefix}_p{index}.csv.gz"
            out = f"/app/resultados/{args.folder}/{filename}"
            command = ["docker", "exec", "gerador", "python", "/app/carga.py", args.system,
                       "--threads", str(threads), "--seconds", str(duration), "--warmup", "0",
                       "--seed", str(seed), "--output", out]
            handle = (root / f"{prefix}_p{index}.log").open("w", encoding="utf-8")
            handles.append(handle)
            procs.append(subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT))
            files.append(filename)
            print(f"Processo {index}: {threads} threads, semente {seed}", flush=True)
        log_event(events, "geradores_iniciados", f"processos={args.processes}")
        time.sleep(args.before)
        if any(pr.poll() is not None for pr in procs):
            raise RuntimeError("Gerador terminou antes da falha; confira os logs")

        # Resolve o papel no instante da falha, não antes da carga inicial.
        leader = etcd_leader() if args.system == "etcd" else None
        target = choose_target(args.system, args.role, leader)
        log_event(events, "alvo_identificado", f"alvo={target}; lider_antes={leader}")
        log_event(events, "falha_solicitada", target)
        run_command("docker", "kill", target)
        fault_active = True
        log_event(events, "no_morto", target)
        time.sleep(args.fault_seconds)
        log_event(events, "reinicio_solicitado", target)
        run_command("docker", "start", target, timeout=40)
        fault_active = False
        log_event(events, "no_reiniciado", target)
        for proc in procs:
            proc.wait(timeout=args.after + 90)
            if proc.returncode:
                raise RuntimeError(f"Gerador falhou, retorno={proc.returncode}; confira {prefix}_p*.log")
        for file in files:
            if not (root / file).is_file() or not (root / (file + ".json")).is_file():
                raise RuntimeError(f"Falta CSV ou metadados para {file}")
        log_event(events, "geradores_finalizados", "")
        manifest.write_text(json.dumps({
            "system": args.system, "experiment": "E6", "role": args.role,
            "target": target, "leader_before": leader, "N_total": args.N,
            "processes": args.processes, "rep": args.rep, "duration_seconds": duration,
            "before": args.before, "fault_seconds": args.fault_seconds,
            "after": args.after, "seed_base": 2026, "started_epoch": started_epoch,
            "files": files, "events": events.name,
            "note": "Clientes Cassandra fixados por nó: erro em coordenador morto não implica indisponibilidade global"
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"E6 finalizado; manifesto: {manifest}")
    finally:
        if fault_active and target:
            print("Restaurando nó após erro/interrupção...", file=sys.stderr)
            subprocess.run(["docker", "start", target], capture_output=True, text=True)
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    main()
