import os
import sys
import unittest
import requests

# Inject mock API key early to prevent client initialization crashes during imports
os.environ["LLM_API_KEY"] = "mock-key-for-testing"

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

class TestLiveIngestion(unittest.TestCase):
    """Integration checks contacting live websites/RSS feeds."""
    
    def test_live_rss_pull(self):
        """Ensure live RSS endpoint pulling parses correctly under non-mock settings."""
        if os.environ.get("SCOUT_TEST_SOURCING") != "live":
            self.skipTest("Skipping live sourcing test. Set SCOUT_TEST_SOURCING=live to run.")
            
        print("\n[LIVE] Fetching a real RSS stream to test feed compatibility...")
        headers = {'User-Agent': 'Mozilla/5.0'}
        # Testing using Shillong Times or similar RSS
        rss_url = "https://theshillongtimes.com/feed/"
        try:
            r = requests.get(rss_url, headers=headers, timeout=10)
            self.assertEqual(r.status_code, 200)
            self.assertIn("rss", r.text.lower())
        except Exception as e:
            self.fail(f"Failed to fetch live RSS: {e}")

if __name__ == '__main__':
    unittest.main()
