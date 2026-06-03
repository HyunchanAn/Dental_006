from unittest.mock import MagicMock, patch

from src.llm import pico_extractor


def test_extract_pico_from_description_success():
    with patch("src.llm.client.LLMClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        mock_instance.get_completion.return_value = """
        {
          "population": "'Aged'[Mesh]",
          "intervention": "'Dental Implants'[Mesh]",
          "comparison": "",
          "outcome": "'Survival Rate'[Mesh]",
          "study_design": "'Comparative Study'[pt]"
        }
        """

        result = pico_extractor.extract_pico_from_description("Test description")

        assert result is not None
        assert "population" in result
        assert result["population"] == '"Aged"[Mesh]'
        assert result["intervention"] == '"Dental Implants"[Mesh]'


def test_extract_pico_from_description_failure():
    with patch("src.llm.client.LLMClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        mock_instance.get_completion.return_value = "invalid response"

        result = pico_extractor.extract_pico_from_description("Test description")

        assert result is None
