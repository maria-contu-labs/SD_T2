import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'gerador'))
sys.path.insert(0, str(Path(__file__).parents[1]))
from carga import data_value
from stale import value_for
from analisar import percentile


def test_values_256_bytes():
    for i in (0, 1, 10000):
        assert len(data_value(3, i)) == 256
        assert len(value_for(i)) == 256
        assert int(value_for(i)[:16]) == i


def test_percentile_no_malformed_values():
    assert percentile([], .99) is None
    assert percentile([2], .99) == 2
    assert percentile([1, 2, 3, 4, 5], .5) == 3
    assert 4 < percentile([1, 2, 3, 4, 5], .95) <= 5
