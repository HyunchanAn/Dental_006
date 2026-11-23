import os
import sys
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.ingest import deduplicator, pubmed, pubtator
from src.llm import pico_extractor


def test_fetch_hit_count_and_suitability():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"esearchresult": {"count": "184"}}
    mock_resp.raise_for_status.return_value = None

    with patch("src.ingest.pubmed.requests.get", return_value=mock_resp) as mock_get:
        cnt = pubmed.fetch_hit_count('"Dental Implants"[Mesh] AND "Aged"[Mesh]')
        assert cnt == 184
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["rettype"] == "count"

    assert pubmed.classify_hit_count_suitability(4)["status"] == "TOO_NARROW"
    assert pubmed.classify_hit_count_suitability(250)["status"] == "OPTIMAL"
    assert pubmed.classify_hit_count_suitability(25000)["status"] == "TOO_BROAD"


def test_generate_three_pico_scope_candidates_and_recommendation():
    llm_json = """
    {
      "candidates": [
        {
          "scope_id": "narrow",
          "label": "Option A (Narrow / Precision)",
          "description": "Strict MeSH + RCT filter",
          "picos": {
            "population": "'Aged'[Mesh]",
            "intervention": "'Dental Implants'[Mesh]",
            "comparison": "'Dentures'[Mesh]",
            "outcome": "'Mastication'[Mesh]",
            "study_design": "'Randomized Controlled Trial'[pt]"
          },
          "query": ""
        },
        {
          "scope_id": "balanced",
          "label": "Option B (Balanced)",
          "description": "Balanced MeSH + tiab",
          "picos": {
            "population": "'Aged'[Mesh] OR 'Elderly'[tiab]",
            "intervention": "'Dental Implants'[Mesh] OR 'Dental Implant*'[tiab]",
            "comparison": "'Denture*'[tiab]",
            "outcome": "'Masticat*'[tiab]",
            "study_design": ""
          },
          "query": ""
        },
        {
          "scope_id": "broad",
          "label": "Option C (Broad / Recall)",
          "description": "Broad recall",
          "picos": {
            "population": "'Aged'[Mesh] OR 'Elderly'[tiab] OR 'Older adult*'[tiab]",
            "intervention": "'Dental Implant*'[tiab] OR 'Implant-supported'[tiab]",
            "comparison": "",
            "outcome": "",
            "study_design": ""
          },
          "query": ""
        }
      ]
    }
    """
    counts = [5, 240, 14500]
    idx_box = {"i": 0}

    def fake_counter(_q: str) -> int:
        val = counts[idx_box["i"]]
        idx_box["i"] += 1
        return val

    with patch("src.llm.client.LLMClient") as mock_llm_cls:
        mock_llm_cls.return_value.get_completion.return_value = llm_json
        cands = pico_extractor.generate_pico_scope_candidates(
            "65세 이상 노인에서 임플란트와 틀니의 저작 효율 비교",
            count_fetcher=fake_counter,
        )

    assert len(cands) == 3
    assert cands[0]["scope_id"] == "narrow"
    assert cands[0]["suitability"] == "TOO_NARROW"
    assert cands[0]["recommended"] is False

    assert cands[1]["scope_id"] == "balanced"
    assert cands[1]["hit_count"] == 240
    assert cands[1]["suitability"] == "OPTIMAL"
    assert cands[1]["recommended"] is True

    assert cands[2]["scope_id"] == "broad"
    assert cands[2]["suitability"] == "TOO_BROAD"


def test_pubtator_search_merge_and_pmid_deduplication():
    rel_q = pubtator.build_pubtator_relation_query(
        "@CHEMICAL_Denosumab", "@DISEASE_Osteonecrosis", relation_type="cause"
    )
    assert rel_q == "relations:cause|@CHEMICAL_Denosumab|@DISEASE_Osteonecrosis"

    mock_search_resp = MagicMock()
    mock_search_resp.raise_for_status.return_value = None
    mock_search_resp.json.return_value = {
        "count": 3,
        "results": [
            {"pmid": 38000001, "title": "Denosumab MRONJ cohort"},
            {"pmid": 38000002, "title": "Bisphosphonate vs Denosumab"},
            {"pmid": 38000003, "title": "Jaw osteonecrosis genetic risk"},
        ],
    }

    with patch("src.ingest.pubtator.requests.get", return_value=mock_search_resp):
        pt_pmids, total = pubtator.search_pubtator_pmids(
            "@CHEMICAL_Denosumab",
            max_ret=3,
            relation_type="cause",
            secondary_entity="@DISEASE_Osteonecrosis",
        )
    assert total == 3
    assert pt_pmids == ["38000001", "38000002", "38000003"]

    merged = pubtator.merge_pubmed_and_pubtator_pmids(
        pubmed_pmids=["38000000", "38000001"],
        pubtator_pmids=pt_pmids,
        max_total=10,
    )
    assert merged["merged_pmids"] == ["38000000", "38000001", "38000002", "38000003"]
    assert merged["overlap_duplicates"] == 1
    assert merged["supplemental_unique_added"] == 2

    existing_df = pd.DataFrame(
        [
            {
                "pmid": "38000001",
                "doi": "10.1000/a",
                "title": "Existing Article Title",
                "first_author": "Kim, H",
                "pub_year": "2025",
            }
        ]
    )
    new_df = pd.DataFrame(
        [
            {
                "pmid": "38000001",
                "doi": "",
                "title": "Slightly Different Subtitled Entry",
                "first_author": "Kim, H",
                "pub_year": "2025",
            },
            {
                "pmid": "38000002",
                "doi": "10.1000/b",
                "title": "Novel PubTator Discovered Trial",
                "first_author": "Lee, S",
                "pub_year": "2025",
            },
        ]
    )
    deduped, stats = deduplicator.deduplicate_records(existing_df, new_df)
    assert stats["duplicates_removed"] == 1
    assert len(deduped) == 1
    assert deduped.iloc[0]["pmid"] == "38000002"
