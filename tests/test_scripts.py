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


import layer_report as L  # noqa: E402


class LayerReportTests(unittest.TestCase):
    def row(self, **kw):
        base = {'id': 'Q1', 'type': '条款', 'required': '4', 'l1': '1', 'l2': '1', 'l3': '1', 'l4': '1', 'refusal': ''}
        base.update(kw)
        return base

    def test_complete_when_all_required_layers_pass(self):
        r = L.evaluate_row(self.row())
        self.assertTrue(r['complete'])
        self.assertEqual(r['achieved'], 4)

    def test_cannot_skip_layers(self):
        # 第 2 层未过，第 4 层标通过：只算到第 1 层，并标记越层
        r = L.evaluate_row(self.row(l2='0', l3='1', l4='1'))
        self.assertEqual(r['achieved'], 1)
        self.assertFalse(r['complete'])
        self.assertTrue(r['skipped'])
        self.assertEqual(r['first_fail'], 2)

    def test_required_layer_lower_than_four(self):
        r = L.evaluate_row(self.row(required='2', l3='0', l4='0'))
        self.assertTrue(r['complete'])

    def test_unrated_stops_chain_and_is_reported(self):
        r = L.evaluate_row(self.row(l2='', l3='', l4=''))
        self.assertEqual(r['achieved'], 1)
        self.assertEqual(r['unrated'], [2, 3, 4])
        self.assertFalse(r['complete'])

    def test_safe_refusal_is_not_complete(self):
        r = L.evaluate_row(self.row(l1='1', l2='1', l3='1', l4='1', refusal='safe'))
        self.assertFalse(r['complete'])
        s = L.summarize([self.row(id='Q1', refusal='safe'), self.row(id='Q2')])
        self.assertEqual(s['complete'], 1)
        self.assertEqual(s['safe_refusal'], ['Q1'])
        self.assertEqual(s['answered'], 1)

    def test_should_refuse_rows_are_reported_separately(self):
        rows = [
            self.row(id='Q1'),
            self.row(id='Q2', should_refuse='1', l1='', l2='', l3='', l4='', refusal='safe'),
            self.row(id='Q3', should_refuse='1', l1='', l2='', l3='', l4='', refusal=''),
        ]
        s = L.summarize(rows)
        self.assertEqual(s['n'], 1)                    # 完成率分母不含应拒答题
        self.assertEqual(s['complete'], 1)
        self.assertEqual(s['should_refuse_n'], 2)
        self.assertEqual(s['refused_correctly'], 1)
        self.assertEqual(s['answered_when_should_refuse'], ['Q3'])
        self.assertEqual(s['safe_refusal'], [])        # 正确拒答不混进“安全拒答”

    def test_should_refuse_cannot_be_wrong_refusal(self):
        with self.assertRaises(ValueError):
            L.evaluate_row(self.row(should_refuse='1', refusal='wrong'))

    def test_bad_values(self):
        with self.assertRaises(ValueError):
            L.evaluate_row(self.row(required='5'))
        with self.assertRaises(ValueError):
            L.evaluate_row(self.row(l1='maybe'))
        with self.assertRaises(ValueError):
            L.evaluate_row(self.row(refusal='x'))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'l.csv'
            with open(p, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['id', 'type', 'required', 'l1', 'l2', 'l3', 'l4', 'refusal', 'should_refuse'])
                w.writeheader()
                w.writerow(self.row(id='Q1'))
                w.writerow(self.row(id='Q2', l2='0', l3='1', l4='0'))
                w.writerow(self.row(id='Q3', refusal='safe'))
                w.writerow(self.row(id='Q4', should_refuse='1', l1='', l2='', l3='', l4='', refusal='safe'))
            L.main(['--input', str(p)])


if __name__ == '__main__':
    unittest.main()
