import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'scripts'))

import audit_sample as A  # noqa: E402
import retrieval_metrics as M  # noqa: E402


class WilsonTests(unittest.TestCase):
    def test_known_interval(self):
        lo, hi = A.wilson(45, 50)
        self.assertAlmostEqual(lo, 0.7864, places=3)
        self.assertAlmostEqual(hi, 0.9565, places=3)

    def test_edges_stay_in_range(self):
        lo, hi = A.wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertGreater(hi, 0.0)
        lo, hi = A.wilson(10, 10)
        self.assertAlmostEqual(hi, 1.0)
        self.assertLess(lo, 1.0)

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            A.wilson(1, 0)
        with self.assertRaises(ValueError):
            A.wilson(6, 5)


class SampleTests(unittest.TestCase):
    def rows(self):
        out = []
        for t, n in (('制度', 60), ('合同', 30), ('扫描件', 10)):
            out += [{'id': '%s%d' % (t, i), 'type': t} for i in range(n)]
        return out

    def test_allocation_sums_and_covers_every_stratum(self):
        picked, quotas = A.draw(self.rows(), 'type', 20, seed=7)
        self.assertEqual(len(picked), 20)
        self.assertEqual(sum(quotas.values()), 20)
        self.assertTrue(all(q >= 1 for q in quotas.values()))
        self.assertEqual(len({r['id'] for r in picked}), 20)

    def test_reproducible_and_seed_sensitive(self):
        a, _ = A.draw(self.rows(), 'type', 20, seed=7)
        b, _ = A.draw(self.rows(), 'type', 20, seed=7)
        c, _ = A.draw(self.rows(), 'type', 20, seed=8)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_errors(self):
        with self.assertRaises(ValueError):
            A.draw(self.rows(), 'type', 2, seed=1)      # n < 层数
        with self.assertRaises(ValueError):
            A.draw(self.rows(), 'type', 1000, seed=1)   # n > 总数

    def test_small_stratum_not_overdrawn(self):
        rows = [{'id': 'a%d' % i, 'type': 'a'} for i in range(100)] + [{'id': 'b0', 'type': 'b'}]
        picked, quotas = A.draw(rows, 'type', 10, seed=1)
        self.assertEqual(quotas['b'], 1)
        self.assertEqual(len(picked), 10)

    def test_cli_rate_from_csv(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'r.csv'
            with open(p, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['id', 'stratum', 'pass'])
                for i in range(8):
                    w.writerow(['d%d' % i, 'pdf', '1' if i < 6 else '0'])
            A.main(['rate', '--results', str(p)])


class RetrievalMetricTests(unittest.TestCase):
    def test_per_item(self):
        d = {'id': 'Q1', 'gold': ['a', 'b'], 'retrieved': ['x', 'a', 'y', 'b']}
        r = M.per_item(d, [1, 2, 4])
        self.assertEqual(r['hit@1'], 0.0)
        self.assertEqual(r['hit@2'], 1.0)
        self.assertAlmostEqual(r['recall@2'], 0.5)
        self.assertAlmostEqual(r['recall@4'], 1.0)
        self.assertAlmostEqual(r['precision@4'], 0.5)
        self.assertAlmostEqual(r['MRR'], 0.5)

    def test_precision_uses_returned_count_when_short(self):
        r = M.per_item({'id': 'Q', 'gold': ['a'], 'retrieved': ['a']}, [5])
        self.assertEqual(r['precision@5'], 1.0)

    def test_evaluate_separates_refusal_and_reports_misses(self):
        items = [
            {'id': 'Q1', 'type': '条款', 'gold': ['a'], 'retrieved': ['a']},
            {'id': 'Q2', 'type': '条款', 'gold': ['b'], 'retrieved': ['x', 'y']},
            {'id': 'Q3', 'type': '拒答', 'gold': [], 'retrieved': ['z']},
        ]
        summary, misses, refuse, returned = M.evaluate(items, [3])
        self.assertEqual(summary['全部']['n'], 2)
        self.assertAlmostEqual(summary['全部']['hit@3'], 0.5)
        self.assertEqual(misses, ['Q2'])
        self.assertEqual(len(refuse), 1)
        self.assertEqual(returned, ['Q3'])
        self.assertNotIn('拒答', summary)

    def test_load_validates(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x.jsonl'
            p.write_text(json.dumps({'id': 'Q1', 'gold': ['a']}) + '\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                M.load(str(p))
            p.write_text('not json\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                M.load(str(p))


if __name__ == '__main__':
    unittest.main()
