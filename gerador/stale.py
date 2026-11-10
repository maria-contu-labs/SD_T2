"""E3: PUT confirmado no n1 seguido de GET no n3, sem sobreposição."""
import argparse
import csv
import gzip
import time
from datetime import datetime, timezone
from pathlib import Path
from clientes import create_adapter


def value_for(seq):
    return (f"{seq:016d}".encode("ascii") + b"s" * 256)[:256]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("system", choices=["etcd", "cassandra"])
    p.add_argument("--pairs", type=int, default=10000)
    p.add_argument("--max-attempts", type=int, default=20000)
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    adapter = create_adapter(args.system, args.timeout)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    completed, confirmed, attempts, stale = 0, 0, 0, 0
    fields = ["inicio_utc", "inicio_epoch", "sistema", "par", "tentativa", "put_ok", "get_ok",
              "versao_confirmada", "versao_lida", "stale", "latencia_put_ms",
              "latencia_get_ms", "erro"]
    with gzip.open(dest, "wt", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        while completed < args.pairs and attempts < args.max_attempts:
            attempts += 1
            v = attempts
            row = {key: "" for key in fields}
            stamp = time.time()
            row.update(inicio_utc=datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                       inicio_epoch=f"{stamp:.6f}", sistema=args.system,
                       par=completed+1, tentativa=attempts, put_ok=0, get_ok=0,
                       versao_confirmada=confirmed, stale="")
            start = time.monotonic()
            try:
                adapter.execute("n1", "PUT", b"chave_e3", value_for(v))
                confirmed = v
                row["put_ok"] = 1
                row["latencia_put_ms"] = round((time.monotonic() - start) * 1000, 4)
            except Exception as exc:
                row["erro"] = "PUT:" + type(exc).__name__
                writer.writerow(row)
                continue  # PUT sem confirmação não entra na contagem de pares válidos
            row["versao_confirmada"] = confirmed
            start = time.monotonic()
            try:
                result = adapter.execute("n3", "GET", b"chave_e3")
                row["latencia_get_ms"] = round((time.monotonic() - start) * 1000, 4)
                row["get_ok"] = 1
                v_read = int(result[:16]) if result is not None else -1
                row["versao_lida"] = v_read
                row["stale"] = int(v_read < confirmed)
                stale += int(v_read < confirmed)
                completed += 1
            except Exception as exc:
                row["erro"] = "GET:" + type(exc).__name__
            writer.writerow(row)
            if completed and completed % 1000 == 0:
                print(f"Pares válidos: {completed}/{args.pairs}, stale: {stale}", flush=True)
    adapter.close()
    print(f"Sistema={args.system}, pares válidos={completed}, stale={stale}, "
          f"taxa={(stale/completed*100 if completed else 0):.4f}%", flush=True)
    if completed < args.pairs:
        raise SystemExit(f"ERRO: necessário {args.pairs} pares válidos; apenas {completed} obtidos")


if __name__ == "__main__":
    main()
