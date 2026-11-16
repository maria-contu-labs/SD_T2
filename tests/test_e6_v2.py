"""Testes offline do fluxo E6_v2; nenhuma chamada Docker."""
import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orch = load_module('orquestrar_e6_v2', 'orquestrar_e6_v2.py')
analysis = load_module('analisar_e6_v2', 'analisar_e6_v2.py')


class E6V2Tests(unittest.TestCase):
    def test_roles(self):
        self.assertEqual(orch.choose_target('etcd', 'lider', 'n3'), 'n3')
        self.assertNotEqual(orch.choose_target('etcd', 'seguidor', 'n3'), 'n3')
        self.assertEqual(orch.choose_target('cassandra', 'coordenador_n1'), 'n1')
        with self.assertRaises(ValueError):
            orch.choose_target('cassandra', 'lider')

    def test_consolidates_per_node_and_preserves_zero_second(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            prefix = 'etcd_lider_n2_r1'
            events = folder / (prefix + '.eventos.csv')
            with events.open('w', newline='') as f:
                wr = csv.writer(f)
                wr.writerow(['epoch', 'instante_utc', 'evento', 'detalhe'])
                wr.writerow([1010, '', 'no_morto', 'n2'])
                wr.writerow([1020, '', 'no_reiniciado', 'n2'])
            names = []
            for i in (0, 1):
                filename = f'{prefix}_p{i}.csv.gz'
                names.append(filename)
                p = folder / filename
                with gzip.open(p, 'wt', newline='') as f:
                    wr = csv.DictWriter(f, fieldnames=['fase', 'inicio_epoch', 'fim_epoch', 'no', 'op', 'ok', 'latencia_ms'])
                    wr.writeheader()
                    wr.writerow({'fase':'medicao','inicio_epoch':1005+i*.1,'fim_epoch':1005.2+i*.1,
                                 'no':'n1','op':'PUT','ok':1,'latencia_ms':1})
                    wr.writerow({'fase':'medicao','inicio_epoch':1011+i*.1,'fim_epoch':1011.2+i*.1,
                                 'no':'n2','op':'PUT','ok':0,'latencia_ms':''})
                    wr.writerow({'fase':'medicao','inicio_epoch':1012+i*.1,'fim_epoch':1012.2+i*.1,
                                 'no':'n3','op':'PUT','ok':1,'latencia_ms':2})
                (folder / (filename+'.json')).write_text(json.dumps({
                    'threads':2,'started_epoch':1000+i*.1,'finished_epoch':1030-i*.1
                }))
            manifest = folder / (prefix+'.manifest.json')
            manifest.write_text(json.dumps({'system':'etcd','role':'lider','target':'n2',
                'N_total':4,'processes':2,'rep':1,'files':names,'events':events.name}))
            summary, node_rows, timeline = analysis.analyze_manifest(manifest)
            self.assertEqual(summary['erros_falha'], 2)
            self.assertEqual(summary['sucessos_falha'], 2)
            self.assertEqual(summary['primeiro_put_sucesso_outro_no_apos_falha_ms'], 2200)
            self.assertTrue(any(r['no']=='n2' and r['fase']=='falha' and r['erros']==2 for r in node_rows))
            self.assertTrue(any(r['segundo_epoch']==1013 and r['sucessos']==0 and r['erros']==0 for r in timeline))


if __name__ == '__main__':
    unittest.main()
