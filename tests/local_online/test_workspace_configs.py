import os
import sys
import unittest
import json

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class TestWorkspaceConfigs(unittest.TestCase):
    """Verifies that local workspace configuration files are valid and structurally sound."""

    def test_sources_configurations(self):
        """Validate sources.json files in sibling scope directories."""
        # Calculate base directory where all repos exist
        # We are in scout-master/tests/local_online
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
        
        scopes = ['scout-local', 'scout-national', 'scout-global']
        
        for scope in scopes:
            scope_path = os.path.join(base_dir, scope)
            if not os.path.exists(scope_path):
                self.skipTest(f"Sibling directory {scope} not found, skipping validation.")
                
            sources_file = os.path.join(scope_path, "data/1/1/sources.json")
            self.assertTrue(os.path.exists(sources_file), f"sources.json is missing in {scope}")
            
            with open(sources_file, 'r', encoding='utf-8') as f:
                try:
                    sources = json.load(f)
                except json.JSONDecodeError as e:
                    self.fail(f"sources.json in {scope} is not valid JSON: {e}")
                    
            self.assertIsInstance(sources, dict, f"sources.json in {scope} should be a dictionary/object")
            
            for key, config in sources.items():
                self.assertIn("name", config, f"Feed config '{key}' in {scope} is missing 'name'")
                self.assertIn("url", config, f"Feed config '{key}' in {scope} is missing 'url'")
                self.assertIn("category", config, f"Feed config '{key}' in {scope} is missing 'category'")
                
if __name__ == '__main__':
    unittest.main()
