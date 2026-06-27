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

class TestMockPipelineFlow(unittest.TestCase):
    def setUp(self):
        self.tmp_workspace = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp_workspace, "data/1/1"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_workspace, "history/local"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_workspace, "tmp"), exist_ok=True)
        
        # Write mock sources.json and scope.txt
        with open(os.path.join(self.tmp_workspace, "scope.txt"), "w") as f:
            f.write("Local\n")
            
        mock_sources = {
            "sentinel": {
                "name": "Sentinel",
                "url": "https://example.com/rss",
                "category": "Local",
                "cleaner_filename": "extract_sentinel.py"
            }
        }
        with open(os.path.join(self.tmp_workspace, "data/1/1/sources.json"), "w") as f:
            json.dump(mock_sources, f)
            
        os.environ["SCOUT_WORKSPACE"] = self.tmp_workspace

    def tearDown(self):
        shutil.rmtree(self.tmp_workspace)
        if "SCOUT_WORKSPACE" in os.environ:
            del os.environ["SCOUT_WORKSPACE"]

    @patch('subprocess.run')
    @patch('requests.get')
    @patch('openai.resources.chat.Completions.create')
    def test_full_offline_pipeline(self, mock_llm, mock_http, mock_subproc):
        """Runs the main.py execution flow with mocked HTTP and LLM replies."""
        # Setup runpy in-process redirect for subprocess execution
        import runpy
        def run_in_process(cmd, *args, **kwargs):
            script_path = cmd[1]
            orig_argv = sys.argv
            sys.argv = cmd[1:]
            try:
                runpy.run_path(script_path, run_name="__main__")
            finally:
                sys.argv = orig_argv
            
            res = MagicMock()
            res.returncode = 0
            return res
            
        mock_subproc.side_effect = run_in_process

        # 1. Mock RSS response
        mock_rss_xml = """<rss version="2.0">
            <channel>
                <item>
                    <title>Major Flood in Northeast India Region</title>
                    <link>https://example.com/story1</link>
                </item>
            </channel>
        </rss>"""
        mock_http.return_value.status_code = 200
        mock_http.return_value.content = mock_rss_xml.encode('utf-8')
        mock_http.return_value.text = "<html><body><article><h1>Major Flood</h1><p>Northeast India faces severe rains.</p></article></body></html>"
        
        # 2. Mock dynamic LLM completions for each phase agent
        def mock_completions_create(model, messages, **kwargs):
            system_prompt = ""
            for m in messages:
                if m.get("role") == "system":
                    system_prompt = m.get("content", "")
            
            system_prompt_lower = system_prompt.lower()
            print(f"      [DEBUG MOCK LLM] Prompt starts with: {system_prompt_lower[:60].strip()}")
            res_data = {}
            
            if "fact checker" in system_prompt_lower or "validator" in system_prompt_lower or "critic" in system_prompt_lower:
                res_data = {"passed": True, "confidence_score": 100, "is_valid": True}
            elif "relevance" in system_prompt_lower:
                res_data = {"skip_indices": []}
            elif "senior" in system_prompt_lower:
                res_data = {"selected_groups": [[1]]}
            elif "grouping" in system_prompt_lower or "group" in system_prompt_lower:
                res_data = {"groups": [[1]]}
            elif "rewrite" in system_prompt_lower or "writer" in system_prompt_lower:
                res_data = {"title": "Rewritten Title", "content": "Rewritten body content about the major flood."}
            elif "metadata" in system_prompt_lower:
                res_data = {"description": "Severe flooding hits Northeast regional areas.", "region": "Assam", "majorTag": "Disasters"}
            elif "tagger" in system_prompt_lower or "correct_tag" in system_prompt_lower:
                res_data = {"tag": "Disasters"}
            else:
                res_data = {"is_valid": True, "title": "Fallback Title", "content": "Fallback content"}
                
            print(f"      [DEBUG MOCK LLM] Matched keys: {list(res_data.keys())} - values: {res_data}")
            mock_choice = MagicMock()
            mock_choice.message.content = json.dumps(res_data)
            mock_reply = MagicMock()
            mock_reply.choices = [mock_choice]
            return mock_reply

        mock_llm.side_effect = mock_completions_create
        
        # Run main runner
        import main
        try:
            main.main()
            success = True
        except SystemExit as e:
            success = (e.code == 0)
        except Exception as e:
            print(f"Pipeline crashed with exception: {e}")
            success = False
            
        self.assertTrue(success, "Pipeline execution failed or crashed.")
        
        # Verify output article is compiled in push/
        push_dir = os.path.join(self.tmp_workspace, "push")
        self.assertTrue(os.path.exists(push_dir), "push/ directory was not created.")
        articles = os.listdir(push_dir)
        self.assertTrue(len(articles) > 0, "No markdown articles were generated in push/")
        self.assertTrue(articles[0].endswith(".md"), "Generated file is not a markdown file.")
        
        # Parse output markdown file and verify format/fields
        md_file_path = os.path.join(push_dir, articles[0])
        with open(md_file_path, "r", encoding="utf-8") as f:
            md_content = f.read()
        
        # Verify frontmatter fields
        self.assertIn('title: "Major Flood"', md_content)
        self.assertIn("category: Local", md_content)
        self.assertIn("region: Assam", md_content)
        self.assertIn("majorTag: Uncategorized", md_content)
        self.assertIn("isAgentGenerated: true", md_content)
        self.assertIn("Rewritten body content about the major flood.", md_content)
        
        # Verify history is correctly logged
        history_file = os.path.join(self.tmp_workspace, "history/local/sentinel_processed.json")
        self.assertTrue(os.path.exists(history_file), "History log was not created.")
        with open(history_file, "r") as f:
            history = json.load(f)
        
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["url"], "https://example.com/story1")
        self.assertEqual(history[0]["status"], "SUCCESS")

    @patch('subprocess.run')
    @patch('requests.get')
    @patch('openai.resources.chat.Completions.create')
    def test_scope_boundary_filtering(self, mock_llm, mock_http, mock_subproc):
        """Verify that an article targeting a non-local region is correctly skipped in Local scope."""
        import runpy
        def run_in_process(cmd, *args, **kwargs):
            script_path = cmd[1]
            orig_argv = sys.argv
            sys.argv = cmd[1:]
            try:
                runpy.run_path(script_path, run_name="__main__")
            finally:
                sys.argv = orig_argv
            res = MagicMock()
            res.returncode = 0
            return res
        mock_subproc.side_effect = run_in_process

        # Mock RSS response returning a national/delhi news title
        mock_rss_xml = """<rss version="2.0">
            <channel>
                <item>
                    <title>Supreme Court Verdict in New Delhi Parliament</title>
                    <link>https://example.com/story_national</link>
                </item>
            </channel>
        </rss>"""
        mock_http.return_value.status_code = 200
        mock_http.return_value.content = mock_rss_xml.encode('utf-8')
        mock_http.return_value.text = "<html><body><article><h1>Delhi verdict</h1><p>National parliament updates.</p></article></body></html>"

        # Curation relevance skips non-Northeast story
        def mock_completions_create(model, messages, **kwargs):
            system_prompt = ""
            for m in messages:
                if m.get("role") == "system":
                    system_prompt = m.get("content", "")
            
            system_prompt_lower = system_prompt.lower()
            res_data = {}
            
            if "relevance" in system_prompt_lower:
                res_data = {"skip_indices": [1]} # Skip candidate 1 (Delhi parliament)
            elif "senior" in system_prompt_lower:
                res_data = {"selected_groups": []}
            else:
                res_data = {"is_valid": True, "title": "Fallback Title"}
                
            mock_choice = MagicMock()
            mock_choice.message.content = json.dumps(res_data)
            mock_reply = MagicMock()
            mock_reply.choices = [mock_choice]
            return mock_reply

        mock_llm.side_effect = mock_completions_create

        import main
        try:
            main.main()
            success = True
        except SystemExit as e:
            success = (e.code == 0)
        except Exception as e:
            success = False
            
        self.assertTrue(success)
        
        # Verify no local articles were written to push since the only candidate was filtered out
        push_dir = os.path.join(self.tmp_workspace, "push")
        if os.path.exists(push_dir):
            articles = os.listdir(push_dir)
            self.assertEqual(len(articles), 0, "Non-local article leaked into Local scope push queue!")

if __name__ == '__main__':
    unittest.main()
