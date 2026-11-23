import json
import re
from typing import Any, Callable, Dict, List, Optional

from src.ingest import pubmed
from src.llm import client as llm_client


def extract_pico_from_description(description, feedback=""):
    """
    Extracts PICO elements from a natural language research topic description using LLM.
    Returns a dictionary with keys: population, intervention, comparison, outcome, study_design.
    """
    llm = llm_client.LLMClient()

    system_prompt = """You are an expert Research Librarian and Systematic Reviewer.
Your task is to analyze the User's research topic description and extract the PICO elements + Study Design.

Return a JSON object with EXACTLY these keys:
- "population": The target population or problem.
- "intervention": The main intervention or exposure.
- "comparison": The comparison or control group (if any).
- "outcome": The outcome of interest.
- "study_design": The most appropriate study design for this question.

IMPORTANT JSON FORMATTING:
- **Use SINGLE QUOTES** for search terms inside the JSON values to avoid syntax errors.
- Example: `"population": "'Aged'[Mesh] OR 'Elderly'[tiab]"` (Correct)
- Do NOT use unescaped double quotes inside the value.

IMPORTANT SEARCH STRATEGY (Based on Pollock & Berge 2017):
1. **Combine MeSH with Text Words**: DO NOT use MeSH alone. Always include free-text synonyms.
   - Example: `'Dental Implants'[Mesh] OR 'Dental Implant*'[tiab] OR 'Implant-supported prosthesis'[tiab]`
2. **Use Truncation (*)**: Use `*` to catch variations (plural, endings).
   - `Randomized` -> `Randomiz*` (catches Randomized, Randomised)
   - `Implant` -> `Implant*` (catches Implants, Implantation)
3. **Handle Age Specifics**:
   - **Map numbers to MeSH**:
     - "65+" or "older" -> `'Aged'[Mesh]` (covers 65-79) OR `'Aged, 80 and over'[Mesh]`
     - "80+" -> `'Aged, 80 and over'[Mesh]`
     - "Child" -> `'Child'[Mesh]`
   - **DO NOT usage raw numbers**: NEVER generate terms like `65[mh]` or `65[Mesh]`.
4. **Valid MeSH Only**:
   - Use `'Patient Satisfaction'[Mesh]`.
   - Do NOT guess MeSH terms. If unsure, use `[tiab]`.
5. **Boolean Logic**: Use OR for synonyms, AND for P-I-C-O.
   - Group synonyms carefully: `('Aged'[Mesh] OR 'Elderly'[tiab])`

Example Input: "65세 이상 환자에서 임플란트 만족도"
Example Output:
{
  "population": "'Aged'[Mesh] OR 'Aged, 80 and over'[Mesh] OR 'Elderly'[tiab]",
  "intervention": "'Dental Implants'[Mesh] OR 'Dental Implant*'[tiab]",
  "comparison": "",
  "outcome": "'Patient Satisfaction'[Mesh] OR 'Satisfaction'[tiab]",
  "study_design": "'Comparative Study'[pt]"
}

Example Input (User mentions old age): "I want to see if dental implants work better than bridges for missing teeth in old people."
Example Output:
{
  "population": "'Aged'[Mesh] OR 'Aged, 80 and over'[Mesh] OR 'Elderly'[tiab] OR 'Geriatric*'[tiab]",
  "intervention": "'Dental Implants'[Mesh] OR 'Dental Implant*'[tiab] OR 'Implant-supported'[tiab]",
  "comparison": "'Denture, Partial, Removable'[Mesh] OR 'Denture*'[tiab] OR 'Bridge*'[tiab]",
  "outcome": "'Survival Rate'[Mesh] OR 'Treatment Outcome'[Mesh] OR 'Prognosis'[tiab] OR 'Success rate'[tiab]",
  "study_design": "'Randomized Controlled Trial'[pt] OR 'Comparative Study'[pt] OR 'Cohort Studies'[Mesh]"
}

Example Input (User mentions NO age): "Implant vs Bridge"
Example Output:
{
  "population": "'Tooth Loss'[Mesh] OR 'Tooth loss'[tiab] OR 'Missing teeth'[tiab]",
  "intervention": "'Dental Implants'[Mesh] OR 'Dental Implant*'[tiab]",
  "comparison": "'Dental Bridges'[Mesh] OR 'Bridge*'[tiab]",
  "outcome": "'Treatment Outcome'[Mesh] OR 'Success'[tiab]",
  "study_design": "'Comparative Study'[pt]"
}
"""
    user_prompt = f"""
Research Topic Description:
---
{description}
---

Extract PICO. Return ONLY the JSON object. Do not include markdown code blocks.
"""
    if feedback:
        user_prompt += f"\n\nFeedback from previous attempt:\n{feedback}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = llm.get_completion(messages)
        if response:
            # Cleanup specific to common LLM issues (markdown blocks)
            clean_response = response.replace("```json", "").replace("```", "").strip()

            # Basic regex to catch json blocks or just the curlies
            match = re.search(r"({[\s\S]*})", clean_response)
            if match:
                data = json.loads(match.group(1))
                # Post-processing: Replace single quotes with double quotes for PubMed
                for key in data:
                    if isinstance(data[key], str):
                        data[key] = data[key].replace("'", '"')
                return data
    except Exception as e:
        print(f"Error extracting PICO: {e}")

    return None


def _format_query_clause(term: Optional[str], default_tag: str = "[tiab]") -> Optional[str]:
    if not term or not str(term).strip():
        return None
    cleaned = str(term).strip().replace("'", '"')
    if "[" in cleaned and "]" in cleaned:
        return f"({cleaned})"
    if " OR " in cleaned or " AND " in cleaned:
        return f"({cleaned})"
    if " " in cleaned:
        return f'"{cleaned}"{default_tag}'
    return f"{cleaned}{default_tag}"


def build_boolean_query_from_picos(picos: Dict[str, Any], scope: str = "balanced") -> str:
    """
    Constructs a PubMed Boolean search query from PICO fields tailored to the requested scope:
    - 'narrow': P AND I AND C AND O AND S (high precision)
    - 'balanced': P AND I AND (C or O if present) (balanced precision/recall)
    - 'broad': P AND I (high recall, dropping restrictive comparison/study_design filters)
    """
    p_clause = _format_query_clause(picos.get("population"))
    i_clause = _format_query_clause(picos.get("intervention"))
    c_clause = _format_query_clause(picos.get("comparison"))
    o_clause = _format_query_clause(picos.get("outcome"))
    s_clause = _format_query_clause(picos.get("study_design"), "[pt]")

    scope_norm = (scope or "balanced").strip().lower()
    if scope_norm == "narrow":
        clauses = [p_clause, i_clause, c_clause, o_clause, s_clause]
    elif scope_norm == "broad":
        clauses = [p_clause, i_clause]
        if not i_clause and o_clause:
            clauses.append(o_clause)
    else:
        clauses = [p_clause, i_clause, c_clause or o_clause]

    return " AND ".join([c for c in clauses if c])


def _derive_three_scopes_from_base_pico(
    base_pico: Dict[str, str], description: str = ""
) -> List[Dict[str, Any]]:
    pop = str(base_pico.get("population", "")).strip().replace("'", '"')
    inter = str(base_pico.get("intervention", "")).strip().replace("'", '"')
    comp = str(base_pico.get("comparison", "")).strip().replace("'", '"')
    outc = str(base_pico.get("outcome", "")).strip().replace("'", '"')
    sdes = str(base_pico.get("study_design", "")).strip().replace("'", '"')

    if not pop and not inter and description.strip():
        tokens = [w for w in re.findall(r"[A-Za-z0-9가-힣]+", description) if len(w) >= 2]
        half = max(1, len(tokens) // 2)
        pop = " ".join(tokens[:half])
        inter = " ".join(tokens[half:]) if len(tokens) > half else pop

    narrow_picos = {
        "population": pop,
        "intervention": inter,
        "comparison": comp,
        "outcome": outc,
        "study_design": sdes or '"Randomized Controlled Trial"[pt] OR "Comparative Study"[pt]',
    }
    balanced_picos = {
        "population": pop,
        "intervention": inter,
        "comparison": comp,
        "outcome": outc,
        "study_design": "",
    }
    broad_picos = {
        "population": pop,
        "intervention": inter,
        "comparison": "",
        "outcome": "",
        "study_design": "",
    }

    return [
        {
            "scope_id": "narrow",
            "label": "Option A (Narrow / Precision)",
            "description": "핵심 MeSH 및 연구설계·비교군 조건을 엄격히 적용한 고정밀 쿼리",
            "picos": narrow_picos,
            "query": build_boolean_query_from_picos(narrow_picos, scope="narrow"),
        },
        {
            "scope_id": "balanced",
            "label": "Option B (Balanced)",
            "description": "MeSH와 주요 Title/Abstract 키워드를 균형 있게 결합한 권장 쿼리",
            "picos": balanced_picos,
            "query": build_boolean_query_from_picos(balanced_picos, scope="balanced"),
        },
        {
            "scope_id": "broad",
            "label": "Option C (Broad / Recall)",
            "description": "동의어 확장 및 부가 제약 완화로 누락 위험을 낮춘 고재현율 쿼리",
            "picos": broad_picos,
            "query": build_boolean_query_from_picos(broad_picos, scope="broad"),
        },
    ]


def generate_pico_scope_candidates(
    description: str,
    feedback: str = "",
    count_fetcher: Optional[Callable[[str], int]] = None,
    email: Optional[str] = None,
    api_key: Optional[str] = None,
    mindate: Optional[str] = None,
    maxdate: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Generates 3 PICO + PubMed query candidates with distinct search scopes
    (Option A: Narrow/Precision, Option B: Balanced, Option C: Broad/Recall)
    and attaches real-time PubMed E-utilities hit counts (`rettype=count`).
    """
    llm = llm_client.LLMClient()
    scope_prompt = """You are an expert Systematic Review Librarian.
Given a plain-language research question, produce 3 distinct PICO + PubMed search query scopes in JSON:
{
  "candidates": [
    {
      "scope_id": "narrow",
      "label": "Option A (Narrow / Precision)",
      "description": "Core MeSH and strict PICO + study design filters",
      "picos": {"population": "...", "intervention": "...", "comparison": "...", "outcome": "...", "study_design": "..."},
      "query": "..."
    },
    {
      "scope_id": "balanced",
      "label": "Option B (Balanced)",
      "description": "Balanced MeSH + Title/Abstract terms",
      "picos": {"population": "...", "intervention": "...", "comparison": "...", "outcome": "...", "study_design": "..."},
      "query": "..."
    },
    {
      "scope_id": "broad",
      "label": "Option C (Broad / Recall)",
      "description": "Expanded synonyms and high-recall P+I focus",
      "picos": {"population": "...", "intervention": "...", "comparison": "", "outcome": "...", "study_design": ""},
      "query": "..."
    }
  ]
}
Use single quotes inside JSON values for PubMed phrases (e.g., `'Dental Implants'[Mesh]`). Return ONLY valid JSON."""

    user_msg = f"Research Question:\n{description}\n"
    if feedback:
        user_msg += f"\nFeedback:\n{feedback}\n"

    candidates: List[Dict[str, Any]] = []
    try:
        raw = llm.get_completion(
            [
                {"role": "system", "content": scope_prompt},
                {"role": "user", "content": user_msg},
            ]
        )
        if raw:
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            match = re.search(r"({[\s\S]*})", cleaned)
            if match:
                parsed = json.loads(match.group(1))
                if isinstance(parsed.get("candidates"), list) and len(parsed["candidates"]) >= 3:
                    for item in parsed["candidates"][:3]:
                        picos_obj = item.get("picos") or {}
                        for k in list(picos_obj.keys()):
                            if isinstance(picos_obj[k], str):
                                picos_obj[k] = picos_obj[k].replace("'", '"')
                        scope_id = str(item.get("scope_id", "balanced")).lower()
                        q_str = str(item.get("query", "")).replace("'", '"').strip()
                        if not q_str:
                            q_str = build_boolean_query_from_picos(picos_obj, scope=scope_id)
                        candidates.append(
                            {
                                "scope_id": scope_id,
                                "label": str(item.get("label", scope_id)),
                                "description": str(item.get("description", "")),
                                "picos": picos_obj,
                                "query": q_str,
                            }
                        )
                elif "population" in parsed or "intervention" in parsed:
                    candidates = _derive_three_scopes_from_base_pico(parsed, description=description)
    except Exception as exc:
        print(f"Warning generating 3-scope PICO candidates: {exc}")

    if len(candidates) < 3:
        base = extract_pico_from_description(description, feedback=feedback) or {}
        candidates = _derive_three_scopes_from_base_pico(base, description=description)

    def _default_counter(q: str) -> int:
        return pubmed.fetch_hit_count(
            q,
            api_key=api_key,
            mindate=mindate,
            maxdate=maxdate,
            email=email,
        )

    counter_fn = count_fetcher or _default_counter
    recommended_idx = 1  # Default to Option B (Balanced)
    for idx, cand in enumerate(candidates):
        hits = int(counter_fn(cand["query"]))
        suitability = pubmed.classify_hit_count_suitability(hits)
        cand["hit_count"] = hits
        cand["suitability"] = suitability["status"]
        cand["guidance"] = suitability["guidance"]

    for idx in (1, 0, 2):
        if idx < len(candidates) and candidates[idx]["suitability"] == "OPTIMAL":
            recommended_idx = idx
            break

    for idx, cand in enumerate(candidates):
        cand["recommended"] = idx == recommended_idx

    return candidates
