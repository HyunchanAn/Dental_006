import json
import os
import re

import pandas as pd

from src.llm import client as llm_client


def screen_abstracts(articles_df, picos_data, checkpoint_csv=None):
    """
    Screens articles based on Title and Abstract using an LLM and PICO criteria.
    Yields progress and results one by one for UI updates and checkpointing.

    Args:
        articles_df (pd.DataFrame): DataFrame containing 'pmid', 'title', 'abstract'.
        picos_data (dict): Dictionary containing PICO elements (population, intervention, etc.).
        checkpoint_csv (str): Path to CSV for saving checkpoints.

    Yields:
        tuple: (current_index, total_count, pmid, result_dict)
    """
    llm = llm_client.LLMClient()

    # Load existing checkpoints to skip already screened articles
    screened_pmids = set()
    if checkpoint_csv and os.path.exists(checkpoint_csv):
        try:
            chk_df = pd.read_csv(checkpoint_csv)
            if "pmid" in chk_df.columns:
                screened_pmids = set(chk_df["pmid"].astype(str).tolist())
        except Exception:
            pass

    # Check LLM connection
    if not llm.get_completion([{"role": "user", "content": "Test"}]):
        for idx, row in articles_df.iterrows():
            pmid = str(row.get("pmid", ""))
            yield (idx + 1, len(articles_df), pmid, {
                "pmid": pmid,
                "screening_decision": "Included",
                "screening_reason": "LLM Unavailable",
                "exclusion_category": ""
            })
        return

    system_prompt = """You are an expert systematic reviewer.
Your task is to screen research papers based on their Title and Abstract to decide if they should be included in a systematic review.
You will be provided with the PICO criteria (Population, Intervention, Comparison, Outcome) and Study Design.
Compare the paper's content with these criteria.

Output Format:
Provide your response in JSON format with three keys:
1. "decision": String, either "Included" or "Excluded".
2. "reason": A brief explanation citing specific criteria matched or missed.
3. "exclusion_category": String. If "decision" is "Excluded", you MUST choose exactly ONE of the following standard categories:
   ["Wrong Study Design", "Target Population Mismatch", "Inappropriate Intervention", "Insufficient Outcome Data"]
   If "decision" is "Included", leave this as an empty string "".

Criteria for Inclusion:
- The paper MUST match the Population and Intervention.
- It should ideally match the Study Design (if specified).
- Outcomes and Comparisons are supportive but strict mismatch might not automatically exclude if the main topic is highly relevant, unless specified otherwise.
- If unsure or if the abstract is missing/vague, default to "Included" for full-text review.
"""

    pico_text = f"""
    Population: {picos_data.get("population", "Any")}
    Intervention: {picos_data.get("intervention", "Any")}
    Comparison: {picos_data.get("comparison", "Any")}
    Outcome: {picos_data.get("outcome", "Any")}
    Study Design: {picos_data.get("study_design", "Any")}
    """

    total = len(articles_df)

    for idx, row in articles_df.iterrows():
        pmid = str(row.get("pmid", "Unknown"))

        if pmid in screened_pmids:
            yield (idx + 1, total, pmid, None) # None indicates skipped
            continue

        title = row.get("title", "No Title")
        abstract = row.get("abstract", "No Abstract")

        user_prompt = f"""
PICO Criteria:
{pico_text}

Paper to Screen:
Title: {title}
Abstract: {abstract}

Is this paper relevant? Return JSON.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = llm.get_completion(messages)
            decision = "Included"
            reason = "Parse Error"
            category = ""

            if response:
                json_match = re.search(r"({[\s\S]*})", response)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        decision = data.get("decision", "Included")
                        reason = data.get("reason", "No reason provided")
                        category = data.get("exclusion_category", "")
                    except json.JSONDecodeError:
                        reason = "JSON Decode Error"
                else:
                    reason = "No JSON found in response"
            else:
                reason = "No response from LLM"

            # Normalize decision
            if "exclude" in decision.lower():
                decision = "Excluded"
                # Validate category
                valid_cats = ["Wrong Study Design", "Target Population Mismatch", "Inappropriate Intervention", "Insufficient Outcome Data"]
                if category not in valid_cats:
                    category = "Target Population Mismatch" # default fallback
            else:
                decision = "Included"
                category = ""

        except Exception as e:
            decision = "Included"
            reason = f"Error during screening: {str(e)}"
            category = ""

        result = {
            "pmid": pmid,
            "screening_decision": decision,
            "screening_reason": reason,
            "exclusion_category": category
        }

        # Checkpointing (save immediately)
        if checkpoint_csv:
            res_df = pd.DataFrame([result])
            if not os.path.exists(checkpoint_csv):
                res_df.to_csv(checkpoint_csv, index=False, encoding="utf-8-sig")
            else:
                res_df.to_csv(checkpoint_csv, mode='a', header=False, index=False, encoding="utf-8-sig")

        yield (idx + 1, total, pmid, result)
