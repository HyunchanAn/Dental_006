import json
import re
import threading

from src.llm import client as llm_client

LLM_SEMAPHORE = threading.Semaphore(1)


def extract_pico_multi_agent(text_snippet):
    """
    Extracts PICO (Population, Intervention, Comparison, Outcome) and Study Design
    using a multi-agent approach. It makes 3 independent LLM calls to reduce hallucination
    and improve extraction quality.

    Args:
        text_snippet (str): The text from which to extract information.

    Returns:
        dict: A merged dictionary containing P, I/C, and O extractions with raw quotes.
    """
    llm = llm_client.LLMClient()

    # --- Agent 1: P-Agent (Population & Study Design) ---
    p_system_prompt = """You are a specialized biomedical data extraction AI (P-Agent).
Your task is to extract the Population/Patients characteristics and Study Design from the text.
Include demographics, sample size, and inclusion/exclusion criteria if available.

CRITICAL INSTRUCTIONS (STRICT COMPLIANCE REQUIRED):
1. Extract information strictly based on the provided text snippet. Do not use external knowledge or mix data from other contexts.
2. If the clear data for a specific field is not found in the text, output '-' instead of guessing.
3. Do not infer or hallucinate missing values.
4. Do NOT confuse baseline demographics or prevalence rates with intervention outcomes. Population must only contain baseline cohort information.
5. If the provided text is empty, contains less than 100 words, or appears to be a stub/error message (e.g., 'Redirecting', 'Not Assessable', 'Login', '403 Forbidden', 'Cloudflare'), DO NOT attempt to extract data. Instead, output '-' for all description fields. DO NOT hallucinate or guess based on outside knowledge.

Return a JSON object with EXACTLY these keys:
{
  "population": {
    "description": "Brief description of the population",
    "sample_size": "Number of participants",
    "raw_quote": "Exact quote from the text supporting this"
  },
  "study_design": {
    "design": "Type of study design (e.g., RCT, Cohort)",
    "raw_quote": "Exact quote from the text supporting this"
  }
}"""
    p_messages = [
        {"role": "system", "content": p_system_prompt},
        {"role": "user", "content": f"Text:\n{text_snippet}\n\nExtract Population and Study Design. Return ONLY JSON."},
    ]

    # --- Agent 2: I/C-Agent (Intervention & Comparison) ---
    ic_system_prompt = """You are a specialized biomedical data extraction AI (I/C-Agent).
Your task is to extract the Intervention (experimental treatment) and Comparison (control treatment) from the text.
Include doses, materials, and protocols if available.

CRITICAL INSTRUCTIONS (STRICT COMPLIANCE REQUIRED):
1. Extract information strictly based on the provided text snippet. Do not use external knowledge or mix data from other contexts.
2. If the clear data for a specific field is not found in the text, output '-' instead of guessing.
3. Do not infer or hallucinate missing values.
4. For the Intervention and Comparison, explicitly classify the subcategory (e.g., prosthesis retention type, implant type, material) if clearly described. If not clearly described, output '-'.
5. If the provided text is empty, contains less than 100 words, or appears to be a stub/error message (e.g., 'Redirecting', 'Not Assessable', 'Login', '403 Forbidden', 'Cloudflare'), DO NOT attempt to extract data. Instead, output '-' for all description fields. DO NOT hallucinate or guess based on outside knowledge.

Return a JSON object with EXACTLY these keys:
{
  "intervention": {
    "description": "Brief description of the intervention",
    "subcategory": "Specific subcategory or type (e.g., Cement-retained vs Screw-retained)",
    "raw_quote": "Exact quote from the text supporting this"
  },
  "comparison": {
    "description": "Brief description of the comparison/control",
    "subcategory": "Specific subcategory or type",
    "raw_quote": "Exact quote from the text supporting this"
  }
}"""
    ic_messages = [
        {"role": "system", "content": ic_system_prompt},
        {"role": "user", "content": f"Text:\n{text_snippet}\n\nExtract Intervention and Comparison. Return ONLY JSON."},
    ]

    # --- Agent 3: O-Agent (Outcome) ---
    o_system_prompt = """You are a specialized biomedical data extraction AI (O-Agent).
Your task is to extract the Outcomes (primary and secondary measures) and Time points from the text.

CRITICAL INSTRUCTIONS (STRICT COMPLIANCE REQUIRED):
1. Extract information strictly based on the provided text snippet. Do not use external knowledge or mix data from other contexts.
2. If the clear data for a specific field is not found in the text, output '-' instead of guessing.
3. Do not infer or hallucinate missing values.
4. Extract standardized measurement scales (e.g., VAS, PD, CAL) and summary statistics (Mean, Standard Deviation, N) ONLY if they are explicitly present in the text snippet. If absent, output '-'.
5. Do NOT confuse baseline demographics, baseline clinical measurements, or pre-existing conditions with intervention outcomes. Outcomes MUST be the results measured AFTER the intervention.
6. If the provided text is empty, contains less than 100 words, or appears to be a stub/error message (e.g., 'Redirecting', 'Not Assessable', 'Login', '403 Forbidden', 'Cloudflare'), DO NOT attempt to extract data. Instead, output '-' for all description fields. DO NOT hallucinate or guess based on outside knowledge.

Return a JSON object with EXACTLY these keys:
{
  "outcome": {
    "description": "Brief description of the outcome measures and time points",
    "scale_metric": "Name of the scale or metric used (e.g., VAS, mm)",
    "statistics_summary": "Extracted Mean, SD, N for the groups (if present)",
    "raw_quote": "Exact quote from the text supporting this"
  }
}"""
    o_messages = [
        {"role": "system", "content": o_system_prompt},
        {"role": "user", "content": f"Text:\n{text_snippet}\n\nExtract Outcome. Return ONLY JSON."},
    ]

    def _call_and_parse(messages):
        try:
            with LLM_SEMAPHORE:
                resp = llm.get_completion(messages)
            if resp:
                match = re.search(r"({[\s\S]*})", resp)
                if match:
                    return json.loads(match.group(1))
        except Exception as e:
            print(f"Extraction error: {e}")
        return {}

    p_data = _call_and_parse(p_messages)
    ic_data = _call_and_parse(ic_messages)
    o_data = _call_and_parse(o_messages)

    # Merge all results
    merged_data = {}
    merged_data.update(p_data)
    merged_data.update(ic_data)
    merged_data.update(o_data)

    return merged_data
