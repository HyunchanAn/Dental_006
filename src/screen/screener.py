import json
import re

import pandas as pd

from src.llm import client as llm_client


def screen_abstracts(articles_df, picos_data):
    """
    Screens articles based on Title and Abstract using an LLM and PICO criteria.

    Args:
        articles_df (pd.DataFrame): DataFrame containing 'pmid', 'title', 'abstract'.
        picos_data (dict): Dictionary containing PICO elements (population, intervention, etc.).

    Returns:
        pd.DataFrame: Original DataFrame with added columns 'screening_decision' and 'screening_reason'.
    """
    print("\n--- Starting Automated Screening (Title/Abstract) ---")

    llm = llm_client.LLMClient()

    # Check LLM connection
    if not llm.get_completion([{"role": "user", "content": "Test"}]):
        print(
            "LLM not connected. Skipping automated screening. All articles will be marked as 'Included' (Manual Review Needed)."
        )
        articles_df["screening_decision"] = "Included"
        articles_df["screening_reason"] = "LLM Unavailable"
        return articles_df

    system_prompt = """You are an expert systematic reviewer. 
Your task is to screen research papers based on their Title and Abstract to decide if they should be included in a systematic review.
You will be provided with the PICO criteria (Population, Intervention, Comparison, Outcome) and Study Design.
Compare the paper's content with these criteria.

Output Format:
Provide your response in JSON format with two keys:
1. "decision": String, either "Included" or "Excluded".
2. "reason": A brief explanation (1-2 sentences) citing specific criteria matched or missed.

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

    results = []

    for index, row in articles_df.iterrows():
        pmid = row.get("pmid", "Unknown")
        title = row.get("title", "No Title")
        abstract = row.get("abstract", "No Abstract")

        print(f"Screening PMID: {pmid}...", end="\r")

        user_prompt = f"""
PICO Criteria:
{pico_text}

Paper to Screen:
Title: {title}
Abstract: {abstract}

Is this paper relevant? Return JSON.
"""
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        try:
            response = llm.get_completion(messages)
            decision = "Included"  # Default
            reason = "Parse Error"

            if response:
                # cleaner regex to capture JSON block or just braces
                json_match = re.search(r"({[\s\S]*})", response)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        decision = data.get("decision", "Included")
                        reason = data.get("reason", "No reason provided")
                    except json.JSONDecodeError:
                        reason = "JSON Decode Error"
                else:
                    reason = "No JSON found in response"
            else:
                reason = "No response from LLM"

            # Normalize decision
            if "exclude" in decision.lower():
                decision = "Excluded"
            else:
                decision = "Included"

        except Exception as e:
            decision = "Included"
            reason = f"Error during screening: {str(e)}"

        results.append({"pmid": pmid, "screening_decision": decision, "screening_reason": reason})

    print(f"\nScreening complete. Processed {len(articles_df)} articles.")

    # Merge results back to DataFrame
    results_df = pd.DataFrame(results)
    # Ensure pmid is same type for merge
    articles_df["pmid"] = articles_df["pmid"].astype(str)
    results_df["pmid"] = results_df["pmid"].astype(str)

    final_df = pd.merge(articles_df, results_df, on="pmid", how="left")
    return final_df
