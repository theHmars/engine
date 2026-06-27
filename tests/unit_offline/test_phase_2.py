import os
import sys
import unittest
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

# Ensure the scripts package is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

from triage import run_relevance_filter, run_senior_curation, main

class TestPhase2Triag(unittest.TestCase):
    def setUp(self):
        # Create isolated workspace for each test
        self.tmp_workspace = tempfile.mkdtemp()
        self.original_workspace = os.environ.get('SCOUT_WORKSPACE')
        os.environ['SCOUT_WORKSPACE'] = self.tmp_workspace
        # Ensure tmp directory exists for script writes
        os.makedirs(os.path.join(self.tmp_workspace, 'tmp'), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_workspace)
        if self.original_workspace is not None:
            os.environ['SCOUT_WORKSPACE'] = self.original_workspace
        else:
            os.environ.pop('SCOUT_WORKSPACE', None)

    # ---------- Relevance Filter Tests ----------
    @patch('agents.picker.picker.call_llm')
    def test_relevance_filter_valid_skip(self, mock_llm):
        """LLM returns a valid skip index; function should filter correctly."""
        candidates = [
            {"title": "A", "url": "a"},
            {"title": "B", "url": "b"},
            {"title": "C", "url": "c"},
        ]
        mock_llm.return_value = {"skip_indices": [2]}
        result = run_relevance_filter(candidates)
        self.assertEqual(len(result), 2)
        self.assertListEqual([c["title"] for c in result], ["A", "C"])

    @patch('agents.picker.picker.call_llm')
    def test_relevance_filter_invalid_skip_then_success(self, mock_llm):
        """LLM first returns out‑of‑bounds index, triggering a retry; second call succeeds with no skips."""
        candidates = [
            {"title": "A", "url": "a"},
            {"title": "B", "url": "b"},
        ]
        # First attempt: invalid index 5, second attempt: valid (empty) skip list
        mock_llm.side_effect = [{"skip_indices": [5]}, {"skip_indices": []}]
        result = run_relevance_filter(candidates, attempts_limit=2)
        # After invalid attempt the function retries and returns the original pool
        self.assertEqual(len(result), 2)
        self.assertListEqual([c["title"] for c in result], ["A", "B"])

    # ---------- Senior Curation Tests ----------
    @patch('agents.picker.picker.call_llm')
    def test_senior_curation_group_merge(self, mock_llm):
        """LLM returns a group with two candidates – expect a merged article structure."""
        candidates = [
            {"title": "First", "url": "u1", "source_name": "S1", "source_key": "k1", "category": "Local", "clean_path": "p1", "content": "c1"},
            {"title": "Second", "url": "u2", "source_name": "S2", "source_key": "k2", "category": "Local", "clean_path": "p2", "content": "c2"},
            {"title": "Third", "url": "u3", "source_name": "S3", "source_key": "k3", "category": "Local", "clean_path": "p3", "content": "c3"},
        ]
        mock_llm.return_value = {"selected_groups": [[1, 2], [3]]}
        result = run_senior_curation(candidates, max_slots=10, attempts_limit=1)
        # Expect three items: first merged (is_merged=True) and third untouched
        self.assertEqual(len(result), 2)
        merged = result[0]
        self.assertTrue(merged.get('is_merged'))
        self.assertEqual(merged['title'], 'First')
        self.assertEqual(len(merged['secondary_sources']), 1)
        self.assertEqual(merged['secondary_sources'][0]['title'], 'Second')
        self.assertEqual(result[1]['title'], 'Third')

    @patch('agents.picker.picker.call_llm')
    @patch('random.sample')
    def test_senior_curation_invalid_indices_fallback(self, mock_random, mock_llm):
        """LLM returns out‑of‑bounds indices; after max attempts, function falls back to random selection."""
        candidates = [
            {"title": f"Item{i}", "url": f"u{i}", "source_name": f"S{i}", "source_key": f"k{i}", "category": "Local", "clean_path": f"p{i}"}
            for i in range(1, 5)
        ]
        # Every attempt returns invalid index 10
        mock_llm.side_effect = [{"selected_groups": [[10]]}] * 3
        # Make random.sample deterministic
        mock_random.side_effect = lambda pool, n: pool[:n]
        result = run_senior_curation(candidates, max_slots=2, attempts_limit=3)
        # Expect fallback to first two candidates (deterministic via mock)
        self.assertEqual(len(result), 2)
        self.assertListEqual([c['title'] for c in result], ['Item1', 'Item2'])

    # ---------- Main Function Tests ----------
    def _write_cleaned_candidates(self, data):
        path = os.path.join(self.tmp_workspace, 'tmp', 'cleaned_candidates.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return path

    @patch('agents.picker.picker.call_llm')
    def test_main_empty_pool_creates_empty_outputs(self, mock_llm):
        """When cleaned_candidates.json contains no items, main should write empty JSON files and exit cleanly."""
        self._write_cleaned_candidates({"new_candidates": [], "archived_candidates_last_48h": []})
        # Ensure LLM is never called – but patch to avoid accidental use
        mock_llm.return_value = {}
        try:
            # main() calls sys.exit(0) – capture it
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 0)
        finally:
            # Verify empty output files exist
            rel_path = os.path.join(self.tmp_workspace, 'tmp', 'relevant_candidates.json')
            chosen_path = os.path.join(self.tmp_workspace, 'tmp', 'chosen_articles.json')
            for p in (rel_path, chosen_path):
                self.assertTrue(os.path.exists(p), f"{p} should exist")
                with open(p, 'r', encoding='utf-8') as f:
                    self.assertEqual(json.load(f), [])

    @patch('agents.picker.picker.call_llm')
    def test_main_full_flow(self, mock_llm):
        """Run main() with a non‑empty cleaned_candidates pool and mocked LLM responses.
        Relevance filter returns the same pool (no skips). Senior curation returns a single group.
        """
        cleaned = {
            "new_candidates": [
                {"title": "News A", "url": "a", "source_name": "SrcA", "source_key": "srca", "category": "Local", "clean_path": "p_a"}
            ],
            "archived_candidates_last_48h": []
        }
        self._write_cleaned_candidates(cleaned)
        # Mock sequence: first call for relevance filter, second for senior curation
        def llm_side_effect(system_prompt, user_content):
            if "relevance" in system_prompt.lower():
                return {"skip_indices": []}
            if "senior" in system_prompt.lower():
                return {"selected_groups": [[1]]}
            return {}
        mock_llm.side_effect = llm_side_effect
        # Run main – should not sys.exit (it only exits on empty pool)
        main()
        # Verify relevant_candidates.json matches input pool (since no skips)
        rel_path = os.path.join(self.tmp_workspace, 'tmp', 'relevant_candidates.json')
        with open(rel_path, 'r', encoding='utf-8') as f:
            relevant = json.load(f)
        self.assertEqual(relevant, cleaned["new_candidates"])
        # Verify chosen_articles.json contains one article (no merging needed)
        chosen_path = os.path.join(self.tmp_workspace, 'tmp', 'chosen_articles.json')
        with open(chosen_path, 'r', encoding='utf-8') as f:
            chosen = json.load(f)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]["title"], "News A")
        self.assertFalse(chosen[0].get("is_merged", False))

if __name__ == '__main__':
    unittest.main()
