import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Inject mock API key early to prevent client initialization crashes during imports
os.environ["LLM_API_KEY"] = "mock-key-for-testing"

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

class TestLLMResilience(unittest.TestCase):
    """Test resilience of agent handlers to OpenAI/LLM failure modes."""
    
    @patch('openai.resources.chat.Completions.create')
    def test_llm_rate_limit_graceful_handling(self, mock_create):
        """Verify pipeline handles RateLimitError or API Connection Errors gracefully in triage."""
        from openai import RateLimitError
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_create.side_effect = RateLimitError(
            message="Rate limit exceeded",
            response=mock_response,
            body={}
        )
        
        from triage import run_relevance_filter
        candidates = [{"title": "Test Title", "url": "https://example.com/test"}]
        
        # triage should catch rate limit errors and continue without crashing, returning the candidates
        result = run_relevance_filter(candidates, attempts_limit=1)
        self.assertEqual(result, candidates)

    @patch('openai.resources.chat.Completions.create')
    def test_llm_malformed_json_resilience(self, mock_create):
        """Verify pipeline handles malformed/broken JSON strings from LLM gracefully in triage."""
        mock_reply = MagicMock()
        mock_reply.choices = [MagicMock()]
        # Invalid JSON: missing closing brace
        mock_reply.choices[0].message.content = '{"is_relevant": true, "reason": "broken'
        mock_create.return_value = mock_reply
        
        from triage import run_relevance_filter
        candidates = [{"title": "Test Title", "url": "https://example.com/test"}]
        
        # triage should handle JSON decoding failure and continue without crashing
        result = run_relevance_filter(candidates, attempts_limit=1)
        self.assertEqual(result, candidates)

if __name__ == '__main__':
    unittest.main()
