import os
import sys
import unittest
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

# Ensure the scripts package is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

from produce import process_candidate, main, parse_embedded_image

class TestPhase4Production(unittest.TestCase):
    def setUp(self):
        # Create isolated workspace for each test
        self.tmp_workspace = tempfile.mkdtemp()
        self.original_workspace = os.environ.get('SCOUT_WORKSPACE')
        os.environ['SCOUT_WORKSPACE'] = self.tmp_workspace
        # Ensure tmp directory exists for script writes
        os.makedirs(os.path.join(self.tmp_workspace, 'tmp'), exist_ok=True)
        # Set up a dummy history structure if needed
        os.makedirs(os.path.join(self.tmp_workspace, 'data', '1', '3'), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_workspace)
        if self.original_workspace is not None:
            os.environ['SCOUT_WORKSPACE'] = self.original_workspace
        else:
            os.environ.pop('SCOUT_WORKSPACE', None)

    # ---------- parse_embedded_image Tests ----------
    def test_parse_embedded_image_extracted(self):
        """Should extract image URLs from various text patterns."""
        self.assertEqual(parse_embedded_image("image link: https://example.com/pic.jpg"), "https://example.com/pic.jpg")
        self.assertEqual(parse_embedded_image("img link: http://example.com/pic.png"), "http://example.com/pic.png")
        self.assertEqual(parse_embedded_image("image: https://example.com/pic.webp"), "https://example.com/pic.webp")
        self.assertEqual(parse_embedded_image("img: https://example.com/pic.gif"), "https://example.com/pic.gif")
        self.assertIsNone(parse_embedded_image("no image link here"))

    # ---------- process_candidate Tests ----------
    @patch('produce.rewrite_article')
    @patch('produce.validate_content')
    @patch('produce.generate_metadata')
    @patch('produce.check_timeout')
    def test_process_candidate_success(self, mock_timeout, mock_meta, mock_val, mock_rewrite):
        """Standard candidate processing where rewrite, validation, and metadata generation succeed."""
        mock_timeout.return_value = False
        mock_rewrite.return_value = "This is the rewritten article content."
        mock_val.return_value = {"passed": True, "confidence_score": 95}
        mock_meta.return_value = {
            "title": "Rewritten Title",
            "description": "Short desc",
            "region": "Meghalaya",
            "majorTag": "Politics"
        }

        candidate = {
            "title": "Original Title",
            "url": "https://example.com/orig",
            "source_name": "SrcName",
            "source_key": "srckey",
            "category": "Local",
            "content": "Original article body content.",
            "featured_image": "https://example.com/feat.jpg"
        }

        result = process_candidate(candidate, start_time=0.0)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Rewritten Title")
        self.assertEqual(result["content"], "This is the rewritten article content.")
        self.assertEqual(result["region"], "Meghalaya")
        self.assertEqual(result["majorTag"], "Politics")
        self.assertEqual(result["featured_image"], "https://example.com/feat.jpg")

    @patch('produce.rewrite_article')
    @patch('produce.validate_content')
    @patch('produce.correct_content')
    @patch('produce.generate_metadata')
    @patch('produce.check_timeout')
    def test_process_candidate_self_correction_loop(self, mock_timeout, mock_meta, mock_correct, mock_val, mock_rewrite):
        """Validation fails first, but corrector agent succeeds on second attempt."""
        mock_timeout.return_value = False
        mock_rewrite.return_value = "Initial bad draft."
        mock_correct.return_value = "Corrected draft."
        mock_val.side_effect = [
            {"passed": False, "fix_instruction": "Fix fact X"},
            {"passed": True, "confidence_score": 90}
        ]
        mock_meta.return_value = {"title": "Title", "majorTag": "Sports"}

        candidate = {"title": "Original Title", "url": "https://a", "category": "Local"}
        result = process_candidate(candidate, start_time=0.0)

        self.assertIsNotNone(result)
        self.assertEqual(result["content"], "Corrected draft.")
        self.assertEqual(mock_correct.call_count, 1)

    @patch('produce.rewrite_article')
    @patch('produce.validate_content')
    @patch('produce.correct_content')
    @patch('produce.check_timeout')
    def test_process_candidate_hard_failure(self, mock_timeout, mock_correct, mock_val, mock_rewrite):
        """Validation fails on all attempts, resulting in candidate drop."""
        mock_timeout.return_value = False
        mock_rewrite.return_value = "Draft"
        mock_correct.return_value = "Corrected Draft"
        mock_val.return_value = {"passed": False, "fix_instruction": "Keep trying"}

        candidate = {"title": "Original Title", "url": "https://a"}
        result = process_candidate(candidate, start_time=0.0)

        self.assertIsNone(result)

    @patch('produce.rewrite_article')
    @patch('produce.validate_content')
    @patch('produce.check_timeout')
    def test_process_candidate_adaptive_timeout_fast_fail(self, mock_timeout, mock_val, mock_rewrite):
        """When check_timeout(limit_minutes=15) is True, max_retries is reduced to 1 (Fast-Fail)."""
        mock_timeout.return_value = True  # Simulated critical timeout reached
        mock_rewrite.return_value = "Draft"
        mock_val.return_value = {"passed": False, "fix_instruction": "Keep trying"}

        candidate = {"title": "Original Title", "url": "https://a"}
        result = process_candidate(candidate, start_time=0.0)

        self.assertIsNone(result)
        # Should only have called validator once, since limit is reduced to 1 retry
        self.assertEqual(mock_val.call_count, 1)

    @patch('produce.rewrite_article')
    @patch('produce.validate_content')
    @patch('produce.generate_metadata')
    @patch('produce.correct_tag')
    def test_process_candidate_tag_whitelist_correction(self, mock_tag_correct, mock_meta, mock_val, mock_rewrite):
        """Invalid tag should trigger correction agent, and default on final failure."""
        mock_rewrite.return_value = "Draft content"
        mock_val.return_value = {"passed": True}
        
        # 1. First case: tag is corrected successfully
        mock_meta.return_value = {"title": "Title", "majorTag": "InvalidTag"}
        mock_tag_correct.return_value = "Tech"  # Valid tag
        candidate = {"title": "Original Title", "url": "https://a"}
        
        res1 = process_candidate(candidate, start_time=0.0)
        self.assertEqual(res1["majorTag"], "Tech")
        self.assertEqual(mock_tag_correct.call_count, 1)

        # 2. Second case: tag correction returns another invalid tag, should fallback to Uncategorized
        mock_tag_correct.reset_mock()
        mock_tag_correct.return_value = "StillInvalid"
        res2 = process_candidate(candidate, start_time=0.0)
        self.assertEqual(res2["majorTag"], "Uncategorized")

    @patch('produce.rewrite_article')
    @patch('produce.validate_content')
    @patch('produce.generate_metadata')
    def test_process_candidate_featured_image_fallback(self, mock_meta, mock_val, mock_rewrite):
        """When candidate has no featured_image, check body or secondary sources."""
        mock_rewrite.return_value = "Draft"
        mock_val.return_value = {"passed": True}
        mock_meta.return_value = {"title": "Title", "majorTag": "Tech"}

        # Case: extract from main candidate content
        cand1 = {
            "title": "Title", 
            "url": "https://a", 
            "content": "Some text image: https://example.com/img.png more text"
        }
        res1 = process_candidate(cand1, start_time=0.0)
        self.assertEqual(res1["featured_image"], "https://example.com/img.png")

        # Case: extract from secondary sources
        cand2 = {
            "title": "Title",
            "url": "https://a",
            "is_merged": True,
            "secondary_sources": [
                {"title": "Sec", "content": "Sample text img link: https://example.com/sec.jpg"}
            ]
        }
        res2 = process_candidate(cand2, start_time=0.0)
        self.assertEqual(res2["featured_image"], "https://example.com/sec.jpg")

    # ---------- main() Execution Tests ----------
    def _write_triaged_candidates(self, data):
        path = os.path.join(self.tmp_workspace, 'tmp', 'triaged_candidates.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return path

    @patch('produce.process_candidate')
    @patch('produce.check_timeout')
    def test_main_empty_candidates(self, mock_timeout, mock_process):
        """When triaged_candidates.json is empty, main should write empty produced_articles and exit 0."""
        self._write_triaged_candidates([])
        try:
            with patch('sys.argv', ['produce.py']):
                with self.assertRaises(SystemExit) as ctx:
                    main()
                self.assertEqual(ctx.exception.code, 0)
        finally:
            produced_path = os.path.join(self.tmp_workspace, 'tmp', 'produced_articles.json')
            self.assertTrue(os.path.exists(produced_path))
            with open(produced_path, 'r') as f:
                self.assertEqual(json.load(f), [])

    @patch('produce.process_candidate')
    @patch('produce.check_timeout')
    def test_main_full_flow(self, mock_timeout, mock_process):
        """Test full main() execution matching successful and failing candidates."""
        mock_timeout.return_value = False
        candidates = [
            {"title": "Cand A", "url": "https://a", "source_key": "srca", "category": "Local"},
            {"title": "Cand B", "url": "https://b", "source_key": "srcb", "category": "Local"},
        ]
        self._write_triaged_candidates(candidates)

        # Mock candidate processing: first succeeds, second fails
        mock_process.side_effect = [
            {"title": "Produced A", "original_url": "https://a", "source_key": "srca", "category": "Local"},
            None
        ]

        with patch('sys.argv', ['produce.py']):
            main()

        # Check produced articles
        produced_path = os.path.join(self.tmp_workspace, 'tmp', 'produced_articles.json')
        self.assertTrue(os.path.exists(produced_path))
        with open(produced_path, 'r') as f:
            produced = json.load(f)
        self.assertEqual(len(produced), 1)
        self.assertEqual(produced[0]["title"], "Produced A")

        # Verify history logs exist and contain correct states
        history_a = os.path.join(self.tmp_workspace, 'history', 'local', 'srca_processed.json')
        history_b = os.path.join(self.tmp_workspace, 'history', 'local', 'srcb_processed.json')
        
        self.assertTrue(os.path.exists(history_a))
        with open(history_a, 'r') as f:
            hist_list_a = json.load(f)
            self.assertEqual(hist_list_a[0]["url"], "https://a")
            self.assertEqual(hist_list_a[0]["status"], "SUCCESS")

        self.assertTrue(os.path.exists(history_b))
        with open(history_b, 'r') as f:
            hist_list_b = json.load(f)
            self.assertEqual(hist_list_b[0]["url"], "https://b")
            self.assertEqual(hist_list_b[0]["status"], "RETRY_FAILED")

    @patch('produce.process_candidate')
    @patch('produce.check_timeout')
    def test_main_timeout_threshold(self, mock_timeout, mock_process):
        """When elapsed time exceeds 20 minutes, stop starting new candidates."""
        candidates = [
            {"title": "Cand A", "url": "https://a", "source_key": "srca", "category": "Local"},
            {"title": "Cand B", "url": "https://b", "source_key": "srcb", "category": "Local"},
        ]
        self._write_triaged_candidates(candidates)

        # Simulate timeout on the second candidate check
        mock_timeout.side_effect = [False, True]
        mock_process.return_value = {"title": "Produced A", "original_url": "https://a"}

        with patch('sys.argv', ['produce.py']):
            main()

        # Verify only one was processed
        self.assertEqual(mock_process.call_count, 1)

if __name__ == '__main__':
    unittest.main()
