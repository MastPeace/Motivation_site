"""Run: python3 -m unittest discover -s tests"""
import os, random, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "generator"))
import daily

THEMES = [
    {"name": "innovation", "keywords": ["ai", "startup", "quantum"]},
    {"name": "rest", "keywords": ["rest", "burnout"]},
]


class PickTheme(unittest.TestCase):
    def pick(self, heads, recent=()):
        return daily.pick_theme(heads, THEMES, ["hope"], random.Random(1), recent)

    def test_short_keyword_is_whole_word(self):
        # "ai" must not match said / again / Spain
        self.assertEqual(self.pick(["He said it again in Spain"])[0], "hope")

    def test_whole_word_short_keyword_matches(self):
        self.assertEqual(self.pick(["New AI model released"])[0], "innovation")

    def test_stem_matches_prefix(self):
        self.assertEqual(self.pick(["Workers face burnouts"])[0], "rest")

    def test_recent_theme_penalised(self):
        heads = ["AI boom", "Startup raises cash", "Take a rest", "Rest day"]
        self.assertEqual(self.pick(heads)[0] in ("innovation", "rest"), True)
        self.assertEqual(self.pick(heads, recent={"innovation"})[0], "rest")

    def test_no_headlines_falls_back(self):
        self.assertEqual(self.pick([]), ("hope", 0, None))


class SelectQuote(unittest.TestCase):
    def test_cooldown_respected(self):
        qs = [{"id": "a", "tags": ["x"]}, {"id": "b", "tags": ["x"]}]
        for seed in range(20):
            got = daily.select_quote(qs, [{"id": "a"}], "x", random.Random(seed))
            self.assertEqual(got["id"], "b")


if __name__ == "__main__":
    unittest.main()
