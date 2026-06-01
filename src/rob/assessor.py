import json
import os
import re

import pandas as pd

from src.llm import client as llm_client
from src.parse import tei_parser


def assess_risk_of_bias(tei_path):
    """
    Assess Risk of Bias for a single article using its TEI XML.
    Returns the assessment as a dictionary.
    """
    llm = llm_client.LLMClient()

    full_text = tei_parser.extract_text_from_tei(tei_path)
    if not full_text:
        return None

    # Limit text length to avoid token limits (approx 10k chars)
    text_snippet = (full_text[:12000] + "...") if len(full_text) > 12000 else full_text

    system_prompt = """You are an expert in Cochrane Risk of Bias assessment tool (RoB 2) and ROBINS-I.
Analyze the provided research paper text and assess the risk of bias for the following domains.

Return a JSON object with EXACTLY these 5 keys:
1. "Randomization" (Selection Bias)
2. "Deviations" (Performance Bias)
3. "MissingData" (Attrition Bias)
4. "Measurement" (Detection Bias)
5. "Reporting" (Reporting Bias)

For each domain, provide:
- "quote": A direct quote from the text that serves as evidence.
- "reasoning": Step-by-step justification based on the quote.
- "level": "Low", "High", or "Some Concerns"

Example Output:
{
  "Randomization": {"quote": "Patients were randomly assigned via computer-generated numbers...", "reasoning": "Proper random sequence generation was explicitly described, indicating minimal selection bias.", "level": "Low"},
  "Deviations": {"quote": "Blinding of participants was not possible...", "reasoning": "Lack of blinding may influence behavior, causing performance bias.", "level": "Some Concerns"},
  "MissingData": {"quote": "The dropout rate was 2%...", "reasoning": "Dropout rate is very low and balanced between groups.", "level": "Low"},
  "Measurement": {"quote": "Outcome measures were objectively recorded...", "reasoning": "Objective measurements reduce the risk of detection bias.", "level": "Low"},
  "Reporting": {"quote": "All pre-specified outcomes were reported...", "reasoning": "No selective reporting bias identified.", "level": "Low"}
}
"""
    user_prompt = f"""
Papers Text:
---
{text_snippet}
---

Assess the Risk of Bias. Return ONLY the JSON object.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = llm.get_completion(messages)
        if response:
            # Basic regex to catch json blocks or just the curlies
            match = re.search(r"({[\s\S]*})", response)
            if match:
                return json.loads(match.group(1))
    except Exception as e:
        print(f"Error evaluating RoB: {e}")

    return None


def batch_assess_rob(tei_dir, output_csv_path):
    """
    Runs RoB assessment for all XML files in the TEI directory.
    Yields progress so the UI can be updated.
    """
    rob_results = []

    tei_files = [f for f in os.listdir(tei_dir) if f.endswith(".xml")]
    if not tei_files:
        return

    total = len(tei_files)
    for idx, tei_file in enumerate(tei_files):
        pmid = tei_file.replace(".xml", "")
        tei_path = os.path.join(tei_dir, tei_file)

        assessment = assess_risk_of_bias(tei_path)

        if assessment:
            flat_result = {"pmid": pmid}
            for domain, details in assessment.items():
                if isinstance(details, dict):
                    flat_result[f"{domain}_Level"] = details.get("level", "Unclear")
                    quote = details.get("quote", "")
                    reasoning = details.get("reasoning", "")
                    flat_result[f"{domain}_Explanation"] = f"Quote: '{quote}' | Reasoning: {reasoning}"
                else:
                    flat_result[domain] = str(details)
            rob_results.append(flat_result)
        
        yield (idx + 1, total, pmid)

    if rob_results:
        df = pd.DataFrame(rob_results)
        df.to_csv(output_csv_path, index=False, encoding="utf-8-sig")
