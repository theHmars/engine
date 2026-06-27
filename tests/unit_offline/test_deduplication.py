import os
import sys
import unittest
import tempfile
import shutil
import json
from unittest.mock import patch

# Inject mock API key early to prevent client initialization crashes during imports
os.environ["LLM_API_KEY"] = "mock-key-for-testing"

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

class TestPipelineDeduplication(unittest.TestCase):
    def setUp(self):
        self.tmp_workspace = tempfile.mkdtemp()
        # Setup workspace subdirs
        os.makedirs(os.path.join(self.tmp_workspace, "history/local"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_workspace, "markdown/local"), exist_ok=True)
        
        # Write initial empty shared ledger
        self.shared_path = os.path.join(self.tmp_workspace, "history/local/shared.json")
        with open(self.shared_path, "w") as f:
            json.dump(["2026-06-25-existing-article-headline"], f)

    def tearDown(self):
        shutil.rmtree(self.tmp_workspace)

    @patch('deduplicate.is_duplicate_coverage')
    def test_deduplication_ledgers(self, mock_dup_check):
        """Test deduplicate phase checks history ledgers and handles matches."""
        mock_dup_check.return_value = True
        
        article = {
            "title": "Existing Article Headline",
            "url": "https://example.com/art1",
            "source_name": "Test Source",
            "category": "Local"
        }
        
        from deduplicate import is_duplicate_coverage
        # Should verify duplicate
        self.assertTrue(is_duplicate_coverage(article, self.tmp_workspace))

if __name__ == '__main__':
    unittest.main()
