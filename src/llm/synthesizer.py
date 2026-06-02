import pandas as pd

from src.llm import client as llm_client


def synthesize_answer(picos, lang="KO"):
    """
    Synthesizes an answer to the PICO question based on extracted data and RoB from the database.
    """
    print("--- Starting Synthesis ---")
    import json
    from src.utils import db_manager

    # 1. Load Data
    extracted_list = []
    rob_list = []
    
    articles_df = db_manager.get_articles_df()
    if not articles_df.empty:
        # PICO
        if "pico_data" in articles_df.columns:
            for _, row in articles_df.iterrows():
                if row.get("pico_data"):
                    try:
                        pico = json.loads(row["pico_data"])
                        extracted_list.append(pico)
                    except Exception as e:
                        print(f"Error reading extracted PICO data: {e}")

        # RoB
        if "rob_data" in articles_df.columns:
            for _, row in articles_df.iterrows():
                if row.get("rob_data"):
                    try:
                        rob = json.loads(row["rob_data"])
                        rob_list.append(rob)
                    except Exception as e:
                        print(f"Error reading RoB data: {e}")

    if not extracted_list:
        return "No extracted data available to synthesize an answer."

    extracted_data = json.dumps(extracted_list, ensure_ascii=False, indent=2)
    rob_data = json.dumps(rob_list, ensure_ascii=False, indent=2)

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
