import os
import sys
import unittest
import tempfile
import shutil

# Ensure test imports can find the scripts package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

from utils import load_scope, ensure_dirs

class TestPhase1Utils(unittest.TestCase):
    def setUp(self):
        # Create isolated workspace for each test
        self.tmp_workspace = tempfile.mkdtemp()
        # Preserve original env var if set
        self.original_workspace = os.environ.get('SCOUT_WORKSPACE')
        os.environ['SCOUT_WORKSPACE'] = self.tmp_workspace

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.tmp_workspace)
        # Restore original env var
        if self.original_workspace is not None:
            os.environ['SCOUT_WORKSPACE'] = self.original_workspace
        else:
            os.environ.pop('SCOUT_WORKSPACE', None)

    def test_load_scope_defaults_to_local_when_missing(self):
        """When no scope.txt exists, load_scope should return the default 'local'."""
        # Ensure no scope.txt file is present
        scope_path = os.path.join(self.tmp_workspace, 'scope.txt')
        if os.path.exists(scope_path):
            os.remove(scope_path)
        self.assertFalse(os.path.exists(scope_path))
        self.assertEqual(load_scope(), 'local')

    def test_load_scope_respects_file_content(self):
        """load_scope should read scope.txt and normalize the value correctly."""
        cases = [
            ('Local', 'local'),
            ('NATIONAL', 'national'),
            ('global', 'international'),  # special mapping
            ('International', 'international'),
            ('  local  ', 'local'),  # whitespace handling
        ]
        for raw, expected in cases:
            with open(os.path.join(self.tmp_workspace, 'scope.txt'), 'w') as f:
                f.write(raw)
            self.assertEqual(load_scope(), expected)

    def test_ensure_dirs_creates_expected_structure(self):
        """ensure_dirs should create the four core data directories for a given source slug."""
        original_cwd = os.getcwd()
        try:
            os.chdir(self.tmp_workspace)
            source_slug = 'testsource'
            ensure_dirs(source_slug)
            expected_dirs = [
                'data/1/1',
                f'data/1/2/cleaned/{source_slug}',
                'data/1/3',
                'data/2'
            ]
            for d in expected_dirs:
                self.assertTrue(os.path.isdir(d), f"Expected directory {d} to exist")
        finally:
            os.chdir(original_cwd)

if __name__ == '__main__':
    unittest.main()
