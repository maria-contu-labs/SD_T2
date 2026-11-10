"""Gerador loop fechado, 80% GET / 20% PUT, 10 mil chaves, valores 256 B.

Uso dentro do contêiner: python /app/carga.py etcd --threads 4 --seconds 120 ...
"""
import argparse
import csv
import gzip
import json
import queue
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from clientes import NODES, create_adapter

FIELDS = ["inicio_utc", "inicio_epoch", "fim_epoch", "sistema", "threads", "worker", "op",
          "chave", "no", "fase", "ok", "latencia_ms", "erro"]
STOP = object()


def now_iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="microseconds")


def data_value(worker_id, counter):
    prefix = f"w{worker_id:04d}-seq{counter:020d}".encode("ascii")
    return (prefix + b"v" * 256)[:256]


def save_records(output, q, n_workers):
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output, "wt", encoding="utf-8", newline="", compresslevel=1) as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        stopped = 0
        while stopped < n_workers:
            rec = q.get()
            if rec is STOP:
                stopped += 1
            else:
                writer.writerow(rec)


def run(args):
    if args.prepare:
        adapter = create_adapter(args.system, args.timeout)
        failures = []
        for i in range(args.keys):
            key = f"k{i:05d}".encode("ascii")
            for attempt in range(3):
                try:
                    adapter.execute("n1", "PUT", key, data_value(0, i))
                    break
                except Exception as exc:
                    if attempt == 2:
                        failures.append((i, type(exc).__name__, str(exc)))
            if (i + 1) % 1000 == 0:
                print(f"Preparadas {i+1}/{args.keys} chaves", flush=True)
        adapter.close()
        if failures:
            raise RuntimeError(f"Nao foi possivel preparar {len(failures)} chaves; exemplos: {failures[:3]}")
        print("Preparacao concluida.")
        return

    adapter = create_adapter(args.system, args.timeout)
    q = queue.Queue(maxsize=args.queue_size)
    out = Path(args.output)
    write_thread = threading.Thread(target=save_records, args=(out, q, args.threads), daemon=False)
    write_thread.start()
    begin = time.monotonic()
    end = begin + args.seconds
    seen = [0] * args.threads

    def client(worker):
        rng = random.Random(args.seed + worker * 104729)
        index = 0
        while True:
            before = time.monotonic()
            if before >= end:
                break
            op = "GET" if rng.random() < 0.8 else "PUT"
            key = f"k{rng.randrange(args.keys):05d}".encode("ascii")
            node = list(NODES)[(worker + index) % len(NODES)]
            start_epoch = time.time()
            ok, error, latency = False, "", ""
            try:
                result = adapter.execute(node, op, key, data_value(worker, index) if op == "PUT" else None)
                # Um GET sem chave é resposta válida do servidor, mas detectamos no E3 separadamente.
                ok = True
                latency = round((time.monotonic() - before) * 1000, 4)
            except Exception as exc:
                error = type(exc).__name__ + ":" + str(exc)[:100].replace("\n", " ")
            finish_epoch = time.time()
            q.put({"inicio_utc": now_iso(start_epoch), "inicio_epoch": f"{start_epoch:.6f}",
                   "fim_epoch": f"{finish_epoch:.6f}", "sistema": args.system,
                   "threads": args.threads, "worker": worker, "op": op,
                   "chave": key.decode("ascii"), "no": node,
                   "fase": "aquecimento" if before - begin < args.warmup else "medicao",
                   "ok": int(ok), "latencia_ms": latency, "erro": error})
            index += 1
        seen[worker] = index
        q.put(STOP)

    threads = [threading.Thread(target=client, args=(i,), daemon=False) for i in range(args.threads)]
    started_epoch = time.time()
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    write_thread.join()
    finished_epoch = time.time()
    adapter.close()
    metadata = {"sistema": args.system, "threads": args.threads, "seed": args.seed,
                "chaves": args.keys, "valor_bytes": 256, "get_fraction": 0.8,
                "duration_seconds": args.seconds, "warmup_seconds": args.warmup,
                "timeout_seconds": args.timeout, "started_epoch": started_epoch,
                "finished_epoch": finished_epoch, "total_attempts": sum(seen)}
    with open(str(out) + ".json", "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)
    print(json.dumps({"saida": str(out), **metadata}, ensure_ascii=False), flush=True)


def parse():
    p = argparse.ArgumentParser()
    p.add_argument("system", choices=["etcd", "cassandra"])
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--seconds", type=int, default=120)
    p.add_argument("--warmup", type=int, default=30)
    p.add_argument("--keys", type=int, default=10000)
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--queue-size", type=int, default=50000)
    p.add_argument("--output", default="/app/resultados/teste.csv.gz")
    p.add_argument("--prepare", action="store_true")
    args = p.parse_args()
    if args.threads < 1 or args.seconds <= 0 or args.warmup < 0 or args.warmup >= args.seconds:
        p.error("threads >= 1, seconds > 0 e 0 <= warmup < seconds")
    return args


if __name__ == "__main__":
    run(parse())
