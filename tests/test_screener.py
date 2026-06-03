import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.screen import screener

def test_screen_abstracts_success():
    with patch("src.llm.client.LLMClient") as mock_client_class, \
         patch("src.utils.db_manager.get_articles_df", return_value=pd.DataFrame()):
        
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        
        # Test Connection true
        mock_instance.get_completion.side_effect = [
            "Test Connection OK", 
            """
            {
              "decision": "Included",
              "reason": "Meets all criteria",
              "exclusion_category": ""
            }
            """
        ]
        
        df = pd.DataFrame({"pmid": ["1"], "title": ["test title"], "abstract": ["test abstract"]})
        generator = screener.screen_abstracts(df, {"population": "test"})
        
        results = list(generator)
        assert len(results) == 1
        
        idx, total, pmid, result = results[0]
        assert result["screening_decision"] == "Included"
        assert result["screening_reason"] == "Meets all criteria"

def test_screen_abstracts_failure():
    with patch("src.llm.client.LLMClient") as mock_client_class, \
         patch("src.utils.db_manager.get_articles_df", return_value=pd.DataFrame()):
        
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        
        # Test Connection true, then invalid response
        mock_instance.get_completion.side_effect = ["Test OK", "invalid response"]
        
        df = pd.DataFrame({"pmid": ["1"], "title": ["test title"], "abstract": ["test abstract"]})
        generator = screener.screen_abstracts(df, {"population": "test"})
        
        results = list(generator)
        assert len(results) == 1
        
        idx, total, pmid, result = results[0]
        assert result["screening_decision"] == "Included"  # Fallback to Included if JSON parse fails
