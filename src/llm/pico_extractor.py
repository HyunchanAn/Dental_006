import json
import re

from src.llm import client as llm_client


def extract_pico_from_description(description):
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
        with open("pico_debug_error.log", "w", encoding="utf-8") as f:
            f.write(f"Error: {e}\n")
            f.write(f"Raw Response: {response}")

    return None
