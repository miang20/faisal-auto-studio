import unittest
from auto_engine import split_script, keywords
from footage import plain

class StudioTests(unittest.TestCase):
    def test_scene_segmentation(self):
        text="This is a short sentence. "*20
        parts=split_script(text)
        self.assertGreaterEqual(len(parts),2)
        self.assertEqual(" ".join(parts)," ".join(text.split()))
    def test_keyword_fallback(self):
        self.assertTrue(keywords("The and they would", "science"))
    def test_html_stripping(self):
        self.assertEqual(plain("<b>A &amp; B</b>"),"A & B")

if __name__=="__main__":
    unittest.main()
