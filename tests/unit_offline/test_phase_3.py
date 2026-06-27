import os
import sys
import unittest
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

# Ensure scripts package is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

from deduplicate import (
    group_chosen_sources,
    merge_grouped_sources,
    run_deduplication,
    compile_triaged_queue,
)

class TestPhase3Deduplication(unittest.TestCase):
    def setUp(self):
        # Isolated workspace
        self.tmp_workspace = tempfile.mkdtemp()
        self.original_workspace = os.environ.get('SCOUT_WORKSPACE')
        os.environ['SCOUT_WORKSPACE'] = self.tmp_workspace
        # Ensure tmp dir exists for script outputs
        os.makedirs(os.path.join(self.tmp_workspace, 'tmp'), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_workspace)
        if self.original_workspace is not None:
            os.environ['SCOUT_WORKSPACE'] = self.original_workspace
        else:
            os.environ.pop('SCOUT_WORKSPACE', None)

    # ---------- group_chosen_sources ----------
    @patch('deduplicate.call_llm')
    def test_group_valid_indices(self, mock_llm):
        """LLM returns proper groups – each article assigned exactly once."""
        chosen = [
            {"title": "A", "content": "Alpha content"},
            {"title": "B", "content": "Beta content"},
            {"title": "C", "content": "Gamma content"},
        ]
        # LLM groups indices 1&2 together, 3 alone
        mock_llm.return_value = {"groups": [[1, 2], [3]]}
        groups = group_chosen_sources(chosen, attempts_limit=1)
        self.assertEqual(len(groups), 2)
        # First group should contain first two dicts
        self.assertListEqual([g['title'] for g in groups[0]], ["A", "B"])
        self.assertListEqual([g['title'] for g in groups[1]], ["C"])

    @patch('deduplicate.call_llm')
    def test_group_invalid_index_retries_then_success(self, mock_llm):
        """First attempt returns out‑of‑bounds index; second attempt succeeds."""
        chosen = [{"title": "X", "content": "x"}, {"title": "Y", "content": "y"}]
        mock_llm.side_effect = [
            {"groups": [[5]]},  # invalid index
            {"groups": [[1]]}   # valid – keep first alone
        ]
        groups = group_chosen_sources(chosen, attempts_limit=2)
        # After retry, should have two singleton groups (unassigned handling adds them)
        self.assertEqual(len(groups), 2)
        self.assertListEqual([g[0]['title'] for g in groups], ["X", "Y"])

    @patch('deduplicate.call_llm')
    def test_group_fallback_all_unique(self, mock_llm):
        """All attempts fail validation – fallback treats each article as its own group."""
        chosen = [{"title": f"T{i}", "content": "c"} for i in range(1, 4)]
        mock_llm.return_value = {"groups": [[10]]}  # always invalid
        groups = group_chosen_sources(chosen, attempts_limit=2)
        # Expect each article wrapped in its own list
        self.assertEqual(len(groups), 3)
        for idx, grp in enumerate(groups, 1):
            self.assertEqual(len(grp), 1)
            self.assertEqual(grp[0]["title"], f"T{idx}")

    # ---------- merge_grouped_sources ----------
    def test_merge_singleton(self):
        article = {"title": "Solo", "url": "u", "source_name": "S", "source_key": "k", "category": "Local", "clean_path": "p"}
        merged = merge_grouped_sources([article])
        self.assertEqual(merged, article)

    def test_merge_multiple(self):
        group = [
            {"title": "Prim", "url": "u1", "source_name": "S1", "source_key": "k1", "category": "Local", "clean_path": "p1", "content": "c1"},
            {"title": "Sec", "url": "u2", "source_name": "S2", "source_key": "k2", "category": "Local", "clean_path": "p2", "content": "c2"},
        ]
        merged = merge_grouped_sources(group)
        self.assertTrue(merged.get('is_merged'))
        self.assertEqual(merged['title'], 'Prim')
        self.assertEqual(len(merged['secondary_sources']), 1)
        self.assertEqual(merged['secondary_sources'][0]['title'], 'Sec')

    # ---------- run_deduplication ----------
    @patch('deduplicate.is_duplicate_coverage')
    def test_run_deduplication_duplicate(self, mock_is_dup):
        mock_is_dup.return_value = True
        article = {"title": "Dup", "url": "u", "source_name": "S", "content": "c"}
        result = run_deduplication(article)
        self.assertFalse(result)
        # Verify update file created and contains article info
        update_path = os.path.join(self.tmp_workspace, 'tmp', 'update_candidates.json')
        self.assertTrue(os.path.exists(update_path))
        with open(update_path, 'r', encoding='utf-8') as f:
            updates = json.load(f)
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]['title'], 'Dup')

    @patch('deduplicate.is_duplicate_coverage')
    def test_run_deduplication_unique(self, mock_is_dup):
        mock_is_dup.return_value = False
        article = {"title": "Unique", "url": "u", "source_name": "S"}
        result = run_deduplication(article)
        self.assertTrue(result)
        # No update file should be written
        update_path = os.path.join(self.tmp_workspace, 'tmp', 'update_candidates.json')
        self.assertFalse(os.path.exists(update_path))

    # ---------- compile_triaged_queue ----------
    def _write_chosen(self, chosen_list):
        path = os.path.join(self.tmp_workspace, 'tmp', 'chosen_articles.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(chosen_list, f, indent=4)
        return path

    @patch('deduplicate.group_chosen_sources')
    @patch('deduplicate.merge_grouped_sources')
    @patch('deduplicate.run_deduplication')
    def test_compile_empty_chosen(self, mock_group, mock_merge, mock_run):
        # Write empty chosen list
        self._write_chosen([])
        # run compile_triaged_queue – should exit gracefully and write empty triaged file
        try:
            compile_triaged_queue()
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        # Verify empty file exists
        triaged_path = os.path.join(self.tmp_workspace, 'tmp', 'triaged_candidates.json')
        self.assertTrue(os.path.exists(triaged_path))
        with open(triaged_path, 'r', encoding='utf-8') as f:
            self.assertEqual(json.load(f), [])

    @patch('deduplicate.group_chosen_sources')
    @patch('deduplicate.merge_grouped_sources')
    @patch('deduplicate.run_deduplication')
    def test_compile_full_flow(self, mock_run, mock_merge, mock_group):
        # Prepare a simple chosen list (content not needed for grouping mock)
        chosen = [{"title": "A", "url": "a", "source_name": "S", "source_key": "k", "category": "Local", "clean_path": "p"}]
        self._write_chosen(chosen)
        # Mock grouping returns list of groups => same as input list wrapped
        mock_group.return_value = [[chosen[0]]]
        # Mock merge simply returns the article unchanged
        mock_merge.side_effect = lambda g: g[0]
        # Mock deduplication says article is unique
        mock_run.return_value = True
        compile_triaged_queue()
        # Verify final triaged file contains the article
        triaged_path = os.path.join(self.tmp_workspace, 'tmp', 'triaged_candidates.json')
        with open(triaged_path, 'r', encoding='utf-8') as f:
            final = json.load(f)
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0]['title'], 'A')

if __name__ == '__main__':
    unittest.main()
