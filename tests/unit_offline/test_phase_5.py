import os
import sys
import unittest
import tempfile
import shutil
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

# Ensure the scripts package is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

from cleanup import main

class TestPhase5Cleanup(unittest.TestCase):
    def setUp(self):
        # Isolated workspace
        self.tmp_workspace = tempfile.mkdtemp()
        self.original_workspace = os.environ.get('SCOUT_WORKSPACE')
        os.environ['SCOUT_WORKSPACE'] = self.tmp_workspace
        # Ensure tmp, history/local and raw dirs exist
        os.makedirs(os.path.join(self.tmp_workspace, 'tmp'), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_workspace, 'tmp', 'raw'), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_workspace, 'history', 'local'), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_workspace, 'push'), exist_ok=True)

        # Write dummy raw html file to test directory deletion
        with open(os.path.join(self.tmp_workspace, 'tmp', 'raw', 'temp.html'), 'w') as f:
            f.write("<html></html>")

    def tearDown(self):
        shutil.rmtree(self.tmp_workspace)
        if self.original_workspace is not None:
            os.environ['SCOUT_WORKSPACE'] = self.original_workspace
        else:
            os.environ.pop('SCOUT_WORKSPACE', None)

    def _write_json(self, name, data):
        path = os.path.join(self.tmp_workspace, 'tmp', name)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return path

    @patch('cleanup.slugify')
    @patch('cleanup.generate_yaml')
    @patch('cleanup.HistoryManager')
    def test_cleanup_full_success_flow(self, mock_hm_class, mock_gen_yaml, mock_slugify):
        """Standard cleanup where produced articles are saved as markdown, backlog is updated, cache is cleared, and callback is written."""
        mock_slugify.side_effect = lambda x: x.lower().replace(" ", "-")
        mock_gen_yaml.return_value = "---\ntitle: test\n---\n"
        
        mock_hm = MagicMock()
        mock_hm_class.return_value = mock_hm

        produced = [
            {
                "title": "Article One",
                "content": "Body text one.",
                "original_url": "https://a",
                "source_name": "Source A",
                "category": "Local"
            }
        ]
        triaged = [
            {
                "title": "Article One",
                "url": "https://a",
                "source_key": "srca"
            }
        ]

        self._write_json("produced_articles.json", produced)
        self._write_json("triaged_candidates.json", triaged)

        # Run cleanup.py main
        with patch('sys.argv', ['cleanup.py']):
            main()

        # 1. Verify markdown output is written to push/
        date_prefix = datetime.now().strftime('%Y-%m-%d')
        expected_md_file = os.path.join(self.tmp_workspace, 'push', f"{date_prefix}-article-one.md")
        self.assertTrue(os.path.exists(expected_md_file))
        with open(expected_md_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertTrue(content.startswith("---\ntitle: test\n---\n"))
            self.assertTrue("Body text one." in content)

        # 2. Verify HistoryManager calls
        mock_hm.log_topic.assert_called_once_with("Article One", "Source A", "Local")
        mock_hm.update_backlog.assert_called_once()
        mock_hm.prune.assert_called_once()

        # 3. Verify raw HTML temp directory was cleaned
        raw_dir = os.path.join(self.tmp_workspace, 'tmp', 'raw')
        self.assertTrue(os.path.exists(raw_dir))
        self.assertEqual(len(os.listdir(raw_dir)), 0)

        # 4. Verify callback json exists
        summary_path = os.path.join(self.tmp_workspace, 'tmp', 'sync_summary.json')
        self.assertTrue(os.path.exists(summary_path))
        with open(summary_path, 'r') as f:
            summary = json.load(f)
            self.assertEqual(summary["status"], "success")
            self.assertEqual(summary["processed_count"], 1)
            self.assertEqual(summary["files_written"], [f"{date_prefix}-article-one.md"])

    @patch('cleanup.HistoryManager')
    def test_cleanup_with_failed_poison_pills(self, mock_hm_class):
        """Any candidates in triaged_candidates that didn't produce output are logged as failed."""
        mock_hm = MagicMock()
        mock_hm_class.return_value = mock_hm

        # Triaged 2 candidates, but only produced 1
        produced = [
            {
                "title": "Success Article",
                "content": "Body text",
                "original_url": "https://success",
                "source_name": "Source A",
                "category": "Local"
            }
        ]
        triaged = [
            {
                "title": "Success Article",
                "url": "https://success",
                "source_key": "srca"
            },
            {
                "title": "Failed Article",
                "url": "https://failed",
                "source_key": "srcb",
                "is_merged": False
            }
        ]

        self._write_json("produced_articles.json", produced)
        self._write_json("triaged_candidates.json", triaged)

        with patch('sys.argv', ['cleanup.py']):
            main()

        # Verify failed candidate was logged
        mock_hm.log_url.assert_called_once_with("https://failed", "srcb", "FAILED_OR_ABANDONED")

    @patch('cleanup.HistoryManager')
    def test_cleanup_missing_produced_file_exits(self, mock_hm_class):
        """When produced_articles.json file is completely missing, cleanup should exit with code 1."""
        # Do not write produced_articles.json
        with patch('sys.argv', ['cleanup.py']):
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 1)

if __name__ == '__main__':
    unittest.main()
