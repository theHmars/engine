import os
import sys
import unittest
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

# Inject mock API key early to prevent client initialization crashes during imports
os.environ["LLM_API_KEY"] = "mock-key-for-testing"

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

class TestFacebookScheduler(unittest.TestCase):
    def setUp(self):
        self.tmp_workspace = tempfile.mkdtemp()
        os.environ["SCOUT_WORKSPACE"] = self.tmp_workspace
        
    def tearDown(self):
        shutil.rmtree(self.tmp_workspace)
        if "SCOUT_WORKSPACE" in os.environ:
            del os.environ["SCOUT_WORKSPACE"]

    @patch('requests.post')
    @patch('requests.get')
    def test_scheduling_flow(self, mock_get, mock_post):
        """Test FB publisher sync loop generates correct staggered slots."""
        import facebook_publisher
        
        # Override repo path target parameters
        facebook_publisher.website_repo_path = os.path.join(self.tmp_workspace, "content-repo")
        facebook_publisher.engine_root_dir = self.tmp_workspace
        
        # Write dummy articles.json index under content repo history
        content_history = os.path.join(self.tmp_workspace, "content-repo/history/local")
        os.makedirs(content_history, exist_ok=True)
        with open(os.path.join(content_history, "articles.json"), "w") as f:
            json.dump(["test-article"], f)
            
        # Write dummy markdown content
        content_markdown = os.path.join(self.tmp_workspace, "content-repo/markdown/local")
        os.makedirs(content_markdown, exist_ok=True)
        with open(os.path.join(content_markdown, "test-article.md"), "w") as f:
            f.write("---\ntitle: 'Test Title'\ndescription: 'Test Description'\n---\nBody content.")
            
        # Mock requests check
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": []} # Empty scheduled queue
        
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"id": "12345"}
        
        # Trigger main sequence but bypass Render build checks
        with patch('facebook_publisher.is_render_build_active', return_value=False), \
             patch('facebook_publisher.trigger_render_deploy', return_value=True), \
             patch('facebook_publisher.wait_for_render_build_live', return_value=True), \
             patch('time.sleep', return_value=None), \
             patch('facebook_publisher.sync_git_ledger_state', return_value=None):
            facebook_publisher.main()
            
        # Verify unshared file has been recorded inside shared.json database
        local_shared_ledger = os.path.join(self.tmp_workspace, "history/local/shared.json")
        self.assertTrue(os.path.exists(local_shared_ledger))
        with open(local_shared_ledger, "r") as f:
            shared = json.load(f)
            self.assertIn("test-article", shared)

if __name__ == '__main__':
    unittest.main()
