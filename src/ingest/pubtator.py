from typing import Any, Dict, List, Optional, Sequence, Tuple
import requests

PUBTATOR3_API_BASE = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"

SUPPORTED_PUBTATOR_RELATIONS = {
    "associate",
    "cause",
    "compare",
    "cotreat",
    "drug_interact",
    "inhibit",
    "interact",
    "negative_correlate",
    "positive_correlate",
    "prevent",
    "stimulate",
    "treat",
}


def _headers(email: Optional[str] = None) -> Dict[str, str]:
    contact = email or "systematic-reviewer-ai@example.com"
    return {
        "User-Agent": f"SystematicReviewerAI/1.1 (mailto:{contact})",
        "Accept": "application/json",
    }


def autocomplete_entity(
    concept_text: str,
    concept_type: Optional[str] = None,
    limit: int = 5,
    email: Optional[str] = None,
    timeout: int = 10,
) -> List[Dict[str, Any]]:
    """
    Resolve free-text biomedical terms (chemical/drug, disease, gene) into normalized
    PubTator 3.0 entity identifiers (e.g. `@DISEASE_Periodontitis`, `@CHEMICAL_Denosumab`).
    """
    if not concept_text or not concept_text.strip():
        return []
    url = f"{PUBTATOR3_API_BASE}/entity/autocomplete/"
    params: Dict[str, Any] = {"query": concept_text.strip()}
    if concept_type:
        params["concept"] = concept_type.strip().lower()
    if limit > 0:
        params["limit"] = int(limit)

    try:
        resp = requests.get(url, params=params, headers=_headers(email), timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list):
            return payload[:limit]
    except (requests.exceptions.RequestException, ValueError) as exc:
        print(f"PubTator 3.0 autocomplete warning: {exc}")
    return []


def build_pubtator_relation_query(
    entity_a: str,
    entity_b: Optional[str] = None,
    relation_type: str = "ANY",
) -> str:
    """
    Construct a PubTator 3.0 relation or entity query expression.
    """
    a_clean = entity_a.strip()
    if not entity_b or not entity_b.strip():
        return a_clean
    rel = (relation_type or "ANY").strip().lower()
    rel_token = rel if rel in SUPPORTED_PUBTATOR_RELATIONS else "ANY"
    return f"relations:{rel_token}|{a_clean}|{entity_b.strip()}"


def search_pubtator_pmids(
    text_query: str,
    max_ret: int = 50,
    relation_type: Optional[str] = None,
    secondary_entity: Optional[str] = None,
    email: Optional[str] = None,
    timeout: int = 12,
) -> Tuple[List[str], int]:
    """
    Query NCBI PubTator 3.0 `/search/` endpoint to retrieve normalized entity/relation
    matched PMIDs as a supplemental ingestion seed alongside PubMed E-utilities.
    """
    if not text_query or not text_query.strip():
        return [], 0

    effective_query = (
        build_pubtator_relation_query(text_query, secondary_entity, relation_type or "ANY")
        if secondary_entity
        else text_query.strip()
    )

    pmids: List[str] = []
    seen = set()
    total_count = 0
    page = 1
    max_pages = max(1, (int(max_ret) + 9) // 10)

    while len(pmids) < max_ret and page <= min(max_pages, 5):
        url = f"{PUBTATOR3_API_BASE}/search/"
        params = {"text": effective_query, "page": page}
        try:
            resp = requests.get(url, params=params, headers=_headers(email), timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except (requests.exceptions.RequestException, ValueError) as exc:
            print(f"PubTator 3.0 search warning (page={page}): {exc}")
            break

        total_count = int(data.get("count", total_count or 0))
        results = data.get("results") or []
        if not results:
            break

        for item in results:
            pmid_val = str(item.get("pmid", "")).strip()
            if pmid_val and pmid_val.isdigit() and pmid_val not in seen:
                seen.add(pmid_val)
                pmids.append(pmid_val)
                if len(pmids) >= max_ret:
                    break
        page += 1

    return pmids, total_count


def merge_pubmed_and_pubtator_pmids(
    pubmed_pmids: Sequence[str],
    pubtator_pmids: Sequence[str],
    max_total: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Deduplicate and merge PubMed primary PMIDs with PubTator 3.0 supplemental PMIDs,
    keeping PubMed priority ordering first.
    """
    merged: List[str] = []
    seen = set()
    pubmed_clean = [str(p).strip() for p in pubmed_pmids if str(p).strip()]
    pubtator_clean = [str(p).strip() for p in pubtator_pmids if str(p).strip()]

    for pmid in pubmed_clean:
        if pmid not in seen:
            seen.add(pmid)
            merged.append(pmid)

    supplemental_added: List[str] = []
    overlap_count = 0
    for pmid in pubtator_clean:
        if pmid in seen:
            overlap_count += 1
            continue
        seen.add(pmid)
        supplemental_added.append(pmid)
        merged.append(pmid)

    if max_total is not None and max_total > 0:
        merged = merged[: int(max_total)]

    return {
        "merged_pmids": merged,
        "pubmed_count": len(pubmed_clean),
        "pubtator_count": len(pubtator_clean),
        "overlap_duplicates": overlap_count,
        "supplemental_unique_added": len(supplemental_added),
        "supplemental_pmids": supplemental_added,
    }
