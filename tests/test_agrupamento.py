"""Testes do agrupamento de processos sem dependência de Docker."""
import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analisar import aggregate_run, percentile


class ConsolidationTests(unittest.TestCase):
    def test_two_processes_one_run(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            manifest = folder / 'cassandra_n4_r1.manifest.json'
            manifest.write_text(json.dumps({'sistema':'cassandra', 'experimento':'PILOTO',
                                            'N_total':4,'processos':2,'seconds':10,'warmup':2}))
            paths = []
            for i, (start, lats) in enumerate(((1000.0,[1,2,3]), (1000.5,[4,5,100]))):
                p = folder / f'cassandra_n4_r1_p{i}.csv.gz'
                paths.append(p)
                Path(str(p)+'.json').write_text(json.dumps({
                    'sistema':'cassandra','threads':2,'duration_seconds':10,
                    'warmup_seconds':2,'started_epoch':start}))
                with gzip.open(p,'wt',newline='') as fh:
                    wr = csv.DictWriter(fh, fieldnames=['fase','inicio_epoch','fim_epoch','ok','op','latencia_ms'])
                    wr.writeheader()
                    for j,lat in enumerate(lats):
                        start_t = 1003 + j
                        wr.writerow({'fase':'medicao','inicio_epoch':start_t,
                                     'fim_epoch':start_t+0.1,'ok':1,'op':'GET','latencia_ms':lat})
            summaries=aggregate_run(paths, manifest)
            total=next(x for x in summaries if x['operacao']=='ALL')
            self.assertEqual(total['N'],4)
            self.assertEqual(total['sucessos'],6)
            self.assertEqual(total['erros'],0)
            self.assertAlmostEqual(total['tempo_medicao_s'],7.5)
            self.assertAlmostEqual(total['vazao_req_s'],.8)
            self.assertAlmostEqual(total['p99_ms'],percentile([1,2,3,4,5,100],.99))
            self.assertGreater(total['p99_ms'],90)  # pooled p99, not mean of separate p99


if __name__ == '__main__':
    unittest.main()
