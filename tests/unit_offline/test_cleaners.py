import os
import sys
import unittest
import tempfile
import shutil

# Inject mock API key early to prevent client initialization crashes during imports
os.environ["LLM_API_KEY"] = "mock-key-for-testing"

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

class TestPipelineCleaners(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.html_file = os.path.join(self.tmp_dir, "test.html")
        self.json_file = os.path.join(self.tmp_dir, "test.json")
        
        # Write dummy HTML content
        with open(self.html_file, "w", encoding="utf-8") as f:
            f.write("<html><body><article><h1>Test Title</h1><p>Test paragraph content.</p></article></body></html>")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_dynamic_extractor_load(self):
        """Verify dynamic import logic inside downloader.py loads local cleaners."""
        from downloader import EXTRACTORS, load_extractors
        load_extractors()
        self.assertIn("sentinel", EXTRACTORS)
        self.assertIn("shillongtimes", EXTRACTORS)

if __name__ == '__main__':
    unittest.main()
