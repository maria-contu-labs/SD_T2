"""Teste isolado da logica E3, sem Docker ou clientes externos."""
import csv
import gzip
import importlib.util
import io
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

class FakeAdapter:
    def __init__(self):
        self.values = {}
        self.calls = []

    def execute(self, node, op, key, value=None):
        self.calls.append((node, op, key))
        if op == 'PUT':
            self.values[key] = value
            return None
        return self.values.get(key)

    def close(self):
        pass


class TestStale(unittest.TestCase):
    def test_chaves_independentes_e_ordem_temporal(self):
        fake_clients = types.ModuleType('clientes')
        adapters = []
        def adapter_factory(system, timeout=2.0):
            adapter = FakeAdapter()
            adapters.append(adapter)
            return adapter
        fake_clients.create_adapter = adapter_factory
        spec = importlib.util.spec_from_file_location('stale_e3_mod', ROOT / 'gerador' / 'stale.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'clientes': fake_clients}):
            spec.loader.exec_module(module)
        keys = []
        with tempfile.TemporaryDirectory() as td:
            for i in range(2):
                path = Path(td) / 'piloto.csv.gz'
                with patch.object(sys, 'argv', ['stale.py', 'cassandra', '--pairs', '4', '--output', str(path)]):
                    with redirect_stdout(io.StringIO()):
                        module.main()
                with gzip.open(path, 'rt', encoding='utf-8') as fh:
                    rows = list(csv.DictReader(fh))
                self.assertEqual(len(rows), 4)
                self.assertTrue(all(row['stale'] == '0' for row in rows))
                keys.append(rows[0]['chave'])
                self.assertEqual(len({row['chave'] for row in rows}), 1)
                self.assertTrue(all(float(row['put_fim_epoch']) <= float(row['get_inicio_epoch'])
                                    for row in rows))
                self.assertEqual([(node, op) for node, op, key in adapters[-1].calls],
                                 [('n1', 'PUT'), ('n3', 'GET')] * 4)
        self.assertNotEqual(keys[0], keys[1])


if __name__ == '__main__':
    unittest.main()
