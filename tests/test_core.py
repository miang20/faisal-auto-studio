import unittest
from auto_engine import split_script, keywords
from footage import plain, items_from_pages

class StudioTests(unittest.TestCase):
    def test_scene_segmentation(self):
        text="This is a short sentence. "*20
        parts=split_script(text)
        self.assertGreaterEqual(len(parts),2)
        self.assertEqual(" ".join(parts)," ".join(text.split()))
    def test_keyword_fallback(self):
        self.assertTrue(keywords("The and they would", "science"))
    def test_commons_license_filter(self):
        pages=[{"title":"File:Test.webm","imageinfo":[{"mime":"video/webm","size":1200,"url":"https://upload.wikimedia.org/example.webm","extmetadata":{"LicenseShortName":{"value":"CC BY-SA 4.0"},"Artist":{"value":"Creator"}}}]}]
        self.assertEqual(len(items_from_pages(pages,8)),1)
        pages[0]["imageinfo"][0]["extmetadata"]["LicenseShortName"]["value"]="All rights reserved"
        self.assertEqual(items_from_pages(pages,8),[])
    def test_html_stripping(self):
        self.assertEqual(plain("<b>A &amp; B</b>"),"A & B")

if __name__=="__main__":
    unittest.main()
