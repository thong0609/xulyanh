import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from approve_tool import digest,encoded,HTTP_CACHE_VERSION
import classify_gallery_script_contexts as refinement


class ContextRefinementTests(unittest.TestCase):
    def classify(self,body):
        page='https://example.org/article';image='https://example.org/image.jpg'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache/http';cache.mkdir(parents=True)
            key=digest(encoded([HTTP_CACHE_VERSION,page,'page']))
            (cache/(key+'.bin')).write_bytes(body.encode())
            (cache/(key+'.json')).write_text(json.dumps({'url':page,'charset':'utf-8'}))
            with patch.object(refinement,'ROOT',root):return refinement.classify(page,image)
    def test_gallery_link_takes_priority_over_script(self):
        result=self.classify('<a href="/image.jpg">Photo</a><script>const image="https://example.org/image.jpg";</script>')
        self.assertEqual(result['category'],'gallery_image_link')
        self.assertTrue(result['also_in_script'])
    def test_json_escaped_image_url_counts_as_script_only(self):
        result=self.classify(r'<script type="application/json">{"image":"https:\/\/example.org\/image.jpg"}</script>')
        self.assertEqual(result['category'],'script_json_only')
    def test_rendered_image_or_other_image_url_does_not_get_script_only_no(self):
        for body in ['<img src="/image.jpg"><script>const image="https://example.org/image.jpg"</script>',
                     '<script>const image="https://other.org/image.jpg"</script>']:
            self.assertEqual(self.classify(body)['category'],'other_unverified_context')

if __name__=='__main__':unittest.main()
