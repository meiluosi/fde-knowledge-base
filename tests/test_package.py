import json
import re
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_links(self):
        for p in R.rglob('*.md'):
            for dest in re.findall(r'\]\(([^)]+)\)', p.read_text()):
                if '://' in dest or dest.startswith('#'):
                    continue
                with self.subTest(file=str(p), link=dest):
                    self.assertTrue((p.parent / dest.split('#')[0]).exists())

    def test_frontmatter(self):
        text = (R / 'SKILL.md').read_text()
        m = re.match(r'---\nname: (.+)\ndescription: (.+)\n---\n', text)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), R.name)

    def test_upstream_fingerprints(self):
        rows = json.loads((R / 'references/upstream-sources.json').read_text())
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertRegex(r['blob_sha'], r'^[0-9a-f]{40}$')

    def test_portable_paths(self):
        for p in list((R / 'references').glob('*.md')) + [R / 'SKILL.md']:
            self.assertNotIn('/Users/', p.read_text())

    def test_skill_links_every_reference_and_template(self):
        skill = (R / 'SKILL.md').read_text()
        for name in ('modes', 'doc-audit', 'knowledge-health', 'fit', 'pipeline',
                     'diagnosis-flow', 'grounding-display', 'eval-set', 'evidence', 'handoff'):
            self.assertIn('references/%s.md' % name, skill)
        for name in ('kb-card', 'doc-audit-sheet', 'governance-charter',
                     'eval-set-sheet', 'diagnosis-log', 'review'):
            self.assertIn('templates/%s.md' % name, skill)

    def test_verdict_words_match_series(self):
        text = (R / 'SKILL.md').read_text()
        for w in ('Proceed', 'Investigate', 'Pivot', 'Stop-Defer'):
            self.assertIn(w, text)

    def test_hard_gates_cap_at_investigate(self):
        text = (R / 'SKILL.md').read_text()
        for key in ('权限与密级', '最多 Investigate'):
            self.assertIn(key, text)

    def test_no_market_data_in_references(self):
        # 产品名、价格等易变事实不入长期规则
        for p in (R / 'references').glob('*.md'):
            if p.name == 'original-material.md':
                continue
            self.assertNotRegex(p.read_text(), r'\$\s?\d|¥\s?\d|元/千')

    def test_behavioral_cases_exist(self):
        rows = [l for l in (R / 'tests/behavioral-cases.md').read_text().splitlines()
                if re.match(r'\| \d+ \|', l)]
        self.assertGreaterEqual(len(rows), 14)

    def test_template_has_no_filled_numbers(self):
        # 判断卡模板是空壳，不预填通过率等数字
        text = (R / 'templates/kb-card.md').read_text()
        self.assertNotRegex(text, r'\d+\s*/\s*\d+\s*=')


if __name__ == '__main__':
    unittest.main()
