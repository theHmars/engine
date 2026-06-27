import os
import sys
import unittest
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Inject mock API key early to prevent client initialization crashes during imports
os.environ["LLM_API_KEY"] = "mock-key-for-testing"

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

class TestPhase1Sourcing(unittest.TestCase):
    def setUp(self):
        self.tmp_workspace = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp_workspace, "tmp"), exist_ok=True)
        os.environ["SCOUT_WORKSPACE"] = self.tmp_workspace
        
    def tearDown(self):
        shutil.rmtree(self.tmp_workspace)
        if "SCOUT_WORKSPACE" in os.environ:
            del os.environ["SCOUT_WORKSPACE"]

    @patch('requests.get')
    def test_scope_isolation(self, mock_get):
        """Verify that get_rss only fetches feeds matching the category scope."""
        # Setup scope.txt
        with open(os.path.join(self.tmp_workspace, "scope.txt"), "w") as f:
            f.write("Local\n")
            
        mock_sources = {
            "sentinel": {
                "name": "Sentinel",
                "url": "https://example.com/rss-local",
                "category": "Local",
                "cleaner_filename": "extract_sentinel.py"
            },
            "thehindu": {
                "name": "The Hindu",
                "url": "https://example.com/rss-national",
                "category": "National",
                "cleaner_filename": "extract_thehindu.py"
            }
        }
        
        # Write dummy cleaner scripts so path validation passes
        cleaners_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "cleaners/local")
        os.makedirs(cleaners_dir, exist_ok=True)
        with open(os.path.join(cleaners_dir, "extract_sentinel.py"), "w") as f:
            f.write("def extract_sentinel(raw, clean): return 'Success'")

        # Mock RSS feed XML content
        mock_rss_xml = """<rss version="2.0">
            <channel>
                <item>
                    <title>Local News Title</title>
                    <link>https://example.com/local-1</link>
                </item>
            </channel>
        </rss>"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = mock_rss_xml.encode('utf-8')

        # Write sources.json
        sources_path = os.path.join(self.tmp_workspace, 'data/1/1/sources.json')
        os.makedirs(os.path.dirname(sources_path), exist_ok=True)
        with open(sources_path, 'w', encoding='utf-8') as f:
            json.dump(mock_sources, f)

        # Run get_rss main
        import get_rss
        import importlib
        importlib.reload(get_rss)
        # Re-patch load_source_history to return empty list
        with patch('get_rss.load_source_history') as mock_hist:
            mock_hist.return_value = []
            get_rss.main()

        # Check discovered_urls.json output
        discovered_path = os.path.join(self.tmp_workspace, "tmp/discovered_urls.json")
        self.assertTrue(os.path.exists(discovered_path))
        with open(discovered_path, "r") as f:
            discovered = json.load(f)

        # Only the "Local" feed (sentinel) should be fetched, "National" (thehindu) skipped
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0]["source_key"], "sentinel")
        self.assertEqual(discovered[0]["title"], "Local News Title")

    @patch('requests.get')
    def test_fetch_rss_valid(self, mock_get):
        """Verify fetch_rss extracts items from valid RSS 2.0."""
        from get_rss import fetch_rss
        
        mock_rss_xml = """<rss version="2.0">
            <channel>
                <item>
                    <title>Standard Local News</title>
                    <link>https://example.com/local-1</link>
                </item>
            </channel>
        </rss>"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = mock_rss_xml.encode('utf-8')
        
        cfg = {"name": "Test Feed", "url": "https://example.com/rss", "category": "Local"}
        results = fetch_rss("test_feed", cfg)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Standard Local News")
        self.assertEqual(results[0]["url"], "https://example.com/local-1")

    @patch('requests.get')
    def test_fetch_rss_atom(self, mock_get):
        """Verify fetch_rss is compatible with Atom format entry namespaces."""
        from get_rss import fetch_rss
        
        mock_atom_xml = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>Atom News Headline</title>
                <link href="https://example.com/atom-1"/>
            </entry>
        </feed>"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = mock_atom_xml.encode('utf-8')
        
        cfg = {"name": "Atom Feed", "url": "https://example.com/atom", "category": "Local"}
        results = fetch_rss("atom_feed", cfg)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Atom News Headline")
        self.assertEqual(results[0]["url"], "https://example.com/atom-1")

    @patch('requests.get')
    def test_fetch_rss_malformed(self, mock_get):
        """Verify fetch_rss handles invalid XML parsing gracefully."""
        from get_rss import fetch_rss
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"<rss><invalid_xml"
        
        cfg = {"name": "Broken Feed", "url": "https://example.com/broken", "category": "Local"}
        results = fetch_rss("broken_feed", cfg)
        self.assertEqual(results, [])

    @patch('requests.get')
    def test_fetch_rss_empty(self, mock_get):
        """Verify fetch_rss processes empty channels gracefully."""
        from get_rss import fetch_rss
        
        mock_rss_xml = """<rss version="2.0"><channel><title>Empty Feed</title></channel></rss>"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = mock_rss_xml.encode('utf-8')
        
        cfg = {"name": "Empty Feed", "url": "https://example.com/empty", "category": "Local"}
        results = fetch_rss("empty_feed", cfg)
        self.assertEqual(results, [])

    @patch('requests.get')
    def test_fetch_rss_blacklist(self, mock_get):
        """Verify fetch_rss filters out blacklisted keyword titles."""
        from get_rss import fetch_rss
        
        mock_rss_xml = """<rss version="2.0">
            <channel>
                <item>
                    <title>Legitimate Local Story</title>
                    <link>https://example.com/legit</link>
                </item>
                <item>
                    <title>Guwahati Teer Result Today Live</title>
                    <link>https://example.com/teer</link>
                </item>
            </channel>
        </rss>"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = mock_rss_xml.encode('utf-8')
        
        cfg = {"name": "Mixed Feed", "url": "https://example.com/mixed", "category": "Local"}
        results = fetch_rss("mixed_feed", cfg)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Legitimate Local Story")

    def test_sourcing_history_deduplication(self):
        """Verify that discovered items already logged in processed logs are discarded."""
        from history_manager import HistoryManager
        
        hm = HistoryManager(self.tmp_workspace)
        hm.log_url("https://example.com/already-processed", "test_src", "SUCCESS")
        
        # Candidate list
        candidates = [
            {"title": "Already Processed", "url": "https://example.com/already-processed", "source_key": "test_src", "category": "Local"},
            {"title": "Fresh Content", "url": "https://example.com/fresh-url", "source_key": "test_src", "category": "Local"}
        ]
        
        # Verify deduplication
        processed_urls = {item["url"] for item in hm.load_source_history("test_src")}
        new_candidates = [c for c in candidates if c["url"] not in processed_urls]
        
        self.assertEqual(len(new_candidates), 1)
        self.assertEqual(new_candidates[0]["url"], "https://example.com/fresh-url")

    def test_corrupted_history_ledger_recovery(self):
        """Verify corrupted processed URL ledger does not crash the system and self-heals."""
        from history_manager import HistoryManager
        
        hm = HistoryManager(self.tmp_workspace)
        history_path = hm._get_history_path("test_src")
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        
        # Write corrupted raw text to the history file
        with open(history_path, "w") as f:
            f.write("{invalid-json-content")
            
        # load_source_history should handle exception, reset it to empty list
        history = hm.load_source_history("test_src")
        self.assertEqual(history, [])

    @patch('requests.get')
    def test_cleaner_script_mismatch_fallback(self, mock_get):
        """Verify get_rss skips a source if its cleaner file does not exist."""
        # Setup scope
        with open(os.path.join(self.tmp_workspace, "scope.txt"), "w") as f:
            f.write("Local\n")
            
        mock_sources = {
            "unsupported_feed": {
                "name": "Unsupported Feed",
                "url": "https://example.com/rss",
                "category": "Local",
                "cleaner_filename": "extract_non_existent.py"
            }
        }
        
        sources_path = os.path.join(self.tmp_workspace, 'data/1/1/sources.json')
        os.makedirs(os.path.dirname(sources_path), exist_ok=True)
        with open(sources_path, 'w', encoding='utf-8') as f:
            json.dump(mock_sources, f)
            
        import get_rss
        # Run get_rss main, it should print warning and skip fetching
        get_rss.main()
        
        # Output discovered_urls.json should be empty
        discovered_path = os.path.join(self.tmp_workspace, "tmp/discovered_urls.json")
        with open(discovered_path, "r") as f:
            discovered = json.load(f)
        self.assertEqual(discovered, [])


class TestPhase1Cleaning(unittest.TestCase):
    def setUp(self):
        self.tmp_workspace = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp_workspace, "tmp"), exist_ok=True)
        os.environ["SCOUT_WORKSPACE"] = self.tmp_workspace
        
    def tearDown(self):
        shutil.rmtree(self.tmp_workspace)
        if "SCOUT_WORKSPACE" in os.environ:
            del os.environ["SCOUT_WORKSPACE"]

    def test_dynamic_cleaner_loading(self):
        """Verify that cleaners are dynamically loaded based on active scope."""
        from clean_html import load_extractors, EXTRACTORS
        
        # Load local scope
        with open(os.path.join(self.tmp_workspace, "scope.txt"), "w") as f:
            f.write("Local\n")
            
        load_extractors(self.tmp_workspace)
        # Verify basic extractor keys are populated in EXTRACTORS map
        self.assertIn("sentinel", EXTRACTORS)
        self.assertIn("shillongtimes", EXTRACTORS)

    @patch('requests.get')
    @patch('clean_html.EXTRACTORS')
    def test_content_extraction_success(self, mock_extractors, mock_get):
        """Verify clean_article processes HTML, writes clean JSON, and removes raw HTML."""
        from clean_html import clean_article
        from history_manager import HistoryManager
        
        hm = HistoryManager(self.tmp_workspace)
        cand = {
            "title": "Local Event News",
            "url": "https://example.com/local-event",
            "source_key": "test_src",
            "source_name": "Test Source",
            "category": "Local"
        }
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "<html><body>Main body text content of the article.</body></html>"
        
        # Extractor successful write
        def dummy_extractor(raw_path, clean_path):
            with open(clean_path, "w") as f:
                json.dump({"title": "Local Event News", "content": "Cleaned article text body."}, f)
            return "Success"
            
        mock_extractors.get.return_value = dummy_extractor
        
        res_data = clean_article(cand, self.tmp_workspace, hm)
        self.assertIsNotNone(res_data)
        self.assertEqual(res_data["content"], "Cleaned article text body.")
        self.assertEqual(res_data["source_key"], "test_src")
        
        # Verify raw HTML was cleaned up
        raw_html_path = os.path.join(self.tmp_workspace, "tmp/raw/test_src/local-event-news.html")
        self.assertFalse(os.path.exists(raw_html_path))

    @patch('requests.get')
    @patch('clean_html.EXTRACTORS')
    def test_selector_layout_failure(self, mock_extractors, mock_get):
        """Verify cleaner Selector Error outputs None and logs failure state."""
        from clean_html import clean_article
        from history_manager import HistoryManager
        
        hm = HistoryManager(self.tmp_workspace)
        cand = {
            "title": "Redesigned Article Layout",
            "url": "https://example.com/redesign",
            "source_key": "test_src",
            "source_name": "Test Source",
            "category": "Local"
        }
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "<html><body>Layout changed</body></html>"
        
        mock_extractors.get.return_value = lambda r, c: "Selector Error"
        
        res_data = clean_article(cand, self.tmp_workspace, hm)
        self.assertIsNone(res_data)
        
        # Verify mapped to failed status in technical ledger
        self.assertTrue(hm.is_url_processed("https://example.com/redesign", "test_src"))
        history = hm.load_source_history("test_src")
        self.assertEqual(history[0]["status"], "FAILED_OR_ABANDONED")

    @patch('requests.get')
    def test_html_download_network_error(self, mock_get):
        """Verify requests network exception logs URL as failed and returns None."""
        from clean_html import clean_article
        from history_manager import HistoryManager
        
        hm = HistoryManager(self.tmp_workspace)
        cand = {
            "title": "Network Timeout Article",
            "url": "https://example.com/timeout",
            "source_key": "test_src",
            "source_name": "Test Source",
            "category": "Local"
        }
        
        # Mock requests.get to throw connection timeout
        mock_get.side_effect = ConnectionError("Connection timed out.")
        
        res_data = clean_article(cand, self.tmp_workspace, hm)
        self.assertIsNone(res_data)
        
        # Mapped to failed status in ledger
        self.assertTrue(hm.is_url_processed("https://example.com/timeout", "test_src"))
        history = hm.load_source_history("test_src")
        self.assertEqual(history[0]["status"], "FAILED_OR_ABANDONED")

    def test_backlog_cache_aging(self):
        """Verify backlog archive prunes entries older than 48 hours."""
        from history_manager import HistoryManager
        
        hm = HistoryManager(self.tmp_workspace)
        
        fresh_time = datetime.now().isoformat()
        old_time = (datetime.now() - timedelta(hours=50)).isoformat()
        
        just_cleaned = [
            {
                "title": "Fresh Item",
                "url": "https://example.com/fresh",
                "source_key": "test_src",
                "cleaned_at": fresh_time
            },
            {
                "title": "Expired Item",
                "url": "https://example.com/expired",
                "source_key": "test_src",
                "cleaned_at": old_time
            }
        ]
        
        # Run backlog update with empty successful urls
        hm.update_backlog(just_cleaned, set())
        
        # Load archive ledger and verify
        self.assertTrue(os.path.exists(hm.archive_path))
        with open(hm.archive_path, "r", encoding="utf-8") as f:
            archive = json.load(f)
            
        # Only fresh item must remain in the archive
        self.assertEqual(len(archive), 1)
        self.assertEqual(archive[0]["title"], "Fresh Item")

    def test_post_processed_backlog_cleanup(self):
        """Verify backlog archive prunes items that were successfully published."""
        from history_manager import HistoryManager
        
        hm = HistoryManager(self.tmp_workspace)
        
        fresh_time = datetime.now().isoformat()
        just_cleaned = [
            {
                "title": "Published Item",
                "url": "https://example.com/published",
                "source_key": "test_src",
                "cleaned_at": fresh_time
            },
            {
                "title": "Unpublished Item",
                "url": "https://example.com/unpublished",
                "source_key": "test_src",
                "cleaned_at": fresh_time
            }
        ]
        
        # Mocking successfully processed URL sets
        successful_urls = {"https://example.com/published"}
        hm.update_backlog(just_cleaned, successful_urls)
        
        with open(hm.archive_path, "r", encoding="utf-8") as f:
            archive = json.load(f)
            
        # Only unpublished item must remain
        self.assertEqual(len(archive), 1)
        self.assertEqual(archive[0]["title"], "Unpublished Item")

if __name__ == '__main__':
    unittest.main()
