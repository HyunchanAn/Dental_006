from unittest.mock import MagicMock

import pandas as pd

from src.ingest import pubmed
from src.screen import screener


def test_fetch_pmids(mocker):
    """
    PubMed E-utilities Search API 호출 및 PMID 반환 규격을 검증합니다.
    """
    mock_response = MagicMock()
    mock_response.json.return_value = {"esearchresult": {"idlist": ["38123456", "38123457"], "count": "2"}}
    mock_response.raise_for_status = MagicMock()

    # requests.get 모듈을 mocking하여 외부 API 네트워크 통신 격리
    mocker.patch("requests.get", return_value=mock_response)

    pmids, total_count = pubmed.fetch_pmids("dental implant satisfaction", max_ret=2)

    assert pmids == ["38123456", "38123457"]
    assert total_count == 2
    mock_response.raise_for_status.assert_called_once()


def test_screen_abstracts(mocker):
    """
    Ollama LLM의 포함/배제 JSON 출력 구문 분석 및 판정 결과 매핑 과정을 검증합니다.
    """
    mock_llm_client = MagicMock()
    # 첫 호출: connection test (성공 응답)
    # 두 번째 호출: PMID 38123456에 대한 스크리닝 성공 JSON 응답
    # 세 번째 호출: PMID 38123457에 대한 스크리닝 제외 JSON 응답
    mock_llm_client.get_completion.side_effect = [
        "Connection successful",
        '{"decision": "Included", "reason": "Patient matches aged population and intervention matches dental implants."}',
        '{"decision": "Excluded", "reason": "Only covers general caries and lacks implant intervention."}',
    ]

    # LLMClient 클래스를 mocking하여 로컬 Ollama 서비스 의존성 격리
    mocker.patch("src.llm.client.LLMClient", return_value=mock_llm_client)

    # 테스트 문헌 데이터프레임
    articles_df = pd.DataFrame(
        [
            {
                "pmid": "38123456",
                "title": "Study on elderly implants",
                "abstract": "Dental implants are highly successful in aged patients.",
            },
            {"pmid": "38123457", "title": "Caries review", "abstract": "Just a general clinical study on cavities."},
        ]
    )

    picos_data = {"population": "Aged", "intervention": "Dental Implants"}

    result_df = screener.screen_abstracts(articles_df, picos_data)

    # 최종 결과 데이터프레임 구조 및 판정 결과 정확도 어설션 검증
    assert "screening_decision" in result_df.columns
    assert "screening_reason" in result_df.columns

    assert result_df.iloc[0]["screening_decision"] == "Included"
    assert "aged population" in result_df.iloc[0]["screening_reason"]

    assert result_df.iloc[1]["screening_decision"] == "Excluded"
    assert "caries" in result_df.iloc[1]["screening_reason"]
