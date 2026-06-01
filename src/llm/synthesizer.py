import pandas as pd

from src.llm import client as llm_client


def synthesize_answer(picos, extracted_csv_path, rob_csv_path, lang="KO"):
    """
    Synthesizes an answer to the PICO question based on extracted data and RoB.
    """
    print("--- Starting Synthesis ---")

    # 1. Load Data
    extracted_data = ""
    if extracted_csv_path and pd.io.common.file_exists(extracted_csv_path):
        try:
            df = pd.read_csv(extracted_csv_path)
            # Convert to a readable string format
            for index, row in df.iterrows():
                extracted_data += f"\n[Study {index + 1}] PMID: {row.get('pmid', 'N/A')}\n"
                extracted_data += f" - Population: {row.get('population', 'N/A')}\n"
                extracted_data += f" - Intervention: {row.get('intervention', 'N/A')}\n"
                extracted_data += f" - Comparison: {row.get('comparison', 'N/A')}\n"
                extracted_data += f" - Outcome: {row.get('outcome', 'N/A')}\n"
                extracted_data += f" - Study Design: {row.get('study_design', 'N/A')}\n"
        except Exception as e:
            print(f"Error reading extracted CSV: {e}")

    rob_data = ""
    if rob_csv_path and pd.io.common.file_exists(rob_csv_path):
        try:
            df = pd.read_csv(rob_csv_path)
            for _index, row in df.iterrows():
                rob_data += f"\n[Study PMID: {row.get('pmid', 'N/A')}]\n"
                # Simplify RoB presentation
                rob_data += f" - Randomization: {row.get('Randomization_Level', 'N/A')}\n"
                rob_data += f" - Deviations: {row.get('Deviations_Level', 'N/A')}\n"
                rob_data += f" - Missing Data: {row.get('MissingData_Level', 'N/A')}\n"
                rob_data += f" - Measurement: {row.get('Measurement_Level', 'N/A')}\n"
                rob_data += f" - Reporting: {row.get('Reporting_Level', 'N/A')}\n"
        except Exception as e:
            print(f"Error reading RoB CSV: {e}")

    if not extracted_data:
        return "No extracted data available to synthesize an answer."

    # 2. Construct Prompt
    llm = llm_client.LLMClient()

    system_prompt = """You are an expert Systematic Reviewer.
Your task is to synthesize the provided evidence (Extracted Data and Risk of Bias assessment) to answer the user's research question (PICO).
Write a comprehensive conclusion in KOREAN.

IMPORTANT FORMATTING RULES:
- NEVER use ** (double asterisks) for bold or emphasis. Write plain text only.
- Use only ## headings for section titles. No bold text anywhere in the body.
- You must write the ACTUAL content based on the provided [Extracted Evidence].
- Do NOT use placeholders like [Insert Argument Here] or [Effect].
- Do NOT output a template. Analyze the specific data provided.
- Terminology Guide:
  - Use professional Korean medical terminology.
  - Translate "dental implant" as "치과 임플란트" or "임플란트", NOT "치아 이식술".
  - If a Korean term is ambiguous, keep the English term in parentheses, e.g., "치관 변위 판막술 (Coronally Advanced Flap, CAF)".

GRADE EVALUATION RULE (CRITICAL):
- If any study has a Risk of Bias (RoB) evaluated as "High Risk" or "High" in any domain, you MUST downgrade the certainty of evidence and explicitly state this limitation in your conclusion. Treat evidence from High Risk studies with extreme caution.

Structure your response as follows:
## 1. 종합 결론 (Conclusion)
Answer the PICO question directly. State clearly if the intervention is effective compared to the comparison based on the evidence.

## 2. 근거 요약 (Summary of Evidence)
Summarize the key findings from the included studies. Mention the quantity and design of studies. Include intervention subcategories and statistical metrics (Mean, SD, N) if they were extracted.

## 3. 근거의 신뢰도 및 GRADE 평가 (Confidence in Evidence & GRADE)
Discuss the overall Risk of Bias. Explicitly mention any studies with "High Risk" and how it downgrades the certainty of your conclusion.

## 4. 임상적 시사점 (Clinical Implications)
Discuss the implications for clinical practice based on the findings.

Output should be in Markdown format. NEVER use ** anywhere.
"""

    user_prompt = f"""
Research Question (PICO):
- Population: {picos.get("population")}
- Intervention: {picos.get("intervention")}
- Comparison: {picos.get("comparison")}
- Outcome: {picos.get("outcome")}

---
[Extracted Evidence]
{extracted_data}

---
[Risk of Bias Assessment]
{rob_data}

---
Based on the above, write the Systemic Review Conclusion (Synthesis) in Korean.
"""

    # 3. Call LLM
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = llm.get_completion(messages)
        return response
    except Exception as e:
        return f"Error during synthesis: {e}"
