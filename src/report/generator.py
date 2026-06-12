from datetime import datetime

import pandas as pd

REPORT_TRANSLATIONS = {
    "EN": {
        "title": "Systematic Review Report",
        "date": "Date",
        "pico_header": "1. Research Question (PICO)",
        "prisma_header": "2. PRISMA Flow Diagram",
        "stats_header": "3. Search & Screening Statistics",
        "stat_total": "Total found in PubMed",
        "stat_screened": "Articles processed/screened",
        "stat_excluded": "Excluded by Title/Abstract",
        "stat_included": "Included for Full Text",
        "stat_retrieved": "Full Text Successfully Retrieved",
        "extract_header": "4. Extracted Data Summary",
        "extract_count": "Total extracted studies",
        "no_extract": "No data extraction results found.",
        "rob_header": "5. Risk of Bias Assessment",
        "rob_count": "Assessed {count} studies.",
        "no_rob": "No Risk of Bias assessment available.",
        "prisma_id": "Identification<br/>Records identified from PubMed",
        "prisma_screened": "Records screened",
        "prisma_excluded": "Records excluded",
        "prisma_sought": "Reports sought for retrieval",
        "prisma_not_retrieved": "Reports not retrieved",
        "prisma_retrieved": "Reports retrieved for eligibility",
        "prisma_included": "Studies included in review",
    },
    "KO": {
        "title": "체계적 문헌고찰 보고서",
        "date": "날짜",
        "pico_header": "1. 연구 질문 (PICO)",
        "prisma_header": "2. PRISMA 흐름도",
        "stats_header": "3. 검색 및 스크리닝 통계",
        "stat_total": "PubMed 검색 결과",
        "stat_screened": "스크리닝된 논문 수",
        "stat_excluded": "제목/초록 스크리닝 제외",
        "stat_included": "원문 검토 대상(포함)",
        "stat_retrieved": "원문(PDF) 확보 성공",
        "extract_header": "4. 데이터 추출 결과 요약",
        "extract_count": "총 추출된 연구 수",
        "no_extract": "추출된 데이터가 없습니다.",
        "rob_header": "5. 비뚤림 위험(RoB) 평가",
        "rob_count": "총 {count}개 연구 평가됨.",
        "no_rob": "평가된 RoB 데이터가 없습니다.",
        "prisma_id": "식별(Identification)<br/>PubMed 검색 결과",
        "prisma_screened": "스크리닝(Screening)<br/>검토된 기록",
        "prisma_excluded": "제외됨(Excluded)",
        "prisma_sought": "적합성 평가 대상<br/>(Reports sought)",
        "prisma_not_retrieved": "원문 미확보<br/>(Not retrieved)",
        "prisma_retrieved": "원문 확보됨<br/>(Retrieved)",
        "prisma_included": "최종 포함<br/>(Included)",
    },
}


def generate_prisma_mermaid(stats, lang="EN"):
    """
    Generates a Mermaid JS code for PRISMA flow diagram.
    """
    s = stats
    t = REPORT_TRANSLATIONS.get(lang, REPORT_TRANSLATIONS["EN"])

    if lang == "KO":
        prisma_id = "식별(Identification)<br/>데이터베이스 검색 결과"
        prisma_dups = "스크리닝 전 제외됨<br/>(중복 문헌)"
    else:
        prisma_id = "Identification<br/>Records identified from Databases"
        prisma_dups = "Records removed before screening<br/>(Duplicate records)"

    gross_total = s.get("gross_total_found", s.get("total_found", 0))
    dups = s.get("duplicates_removed", 0)

    # Custom HTML/CSS PRISMA Flowchart to perfectly match academic layout requirements
    mermaid_code = f"""
<div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; max-width: 800px; margin: 20px auto; color: #1e293b; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid #e2e8f0;">

  <!-- Identification -->
  <div style="display: flex; margin-bottom: 0;">
    <div style="width: 40px; background-color: #43b09c; color: white; display: flex; align-items: center; justify-content: center; writing-mode: vertical-rl; transform: rotate(180deg); font-weight: bold; letter-spacing: 2px; padding: 10px 0; border-radius: 4px;">
      Identification
    </div>
    <div style="flex-grow: 1; padding-left: 20px; display: flex; align-items: center; min-height: 80px;">
      <div style="border: 1px solid #64748b; padding: 15px; background: #f8fafc; width: 300px; text-align: left; border-radius: 2px; box-shadow: 2px 2px 0px rgba(0,0,0,0.05);">
        <b>{prisma_id}</b><br/>(n = {gross_total})
      </div>
      <div style="width: 50px; height: 2px; background-color: #64748b; position: relative;">
        <div style="position: absolute; right: -2px; top: -4px; width: 0; height: 0; border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 6px solid #64748b;"></div>
      </div>
      <div style="border: 1px solid #64748b; padding: 15px; background: #f1f5f9; width: 250px; text-align: left; border-radius: 2px; box-shadow: 2px 2px 0px rgba(0,0,0,0.05);">
        <b>{prisma_dups}</b><br/>(n = {dups})
      </div>
    </div>
  </div>

  <!-- Arrow 1 -->
  <div style="display: flex; height: 30px;">
    <div style="width: 40px;"></div>
    <div style="flex-grow: 1; padding-left: 20px; position: relative;">
      <div style="position: absolute; left: 170px; top: 0; height: 100%; width: 2px; background-color: #64748b;"></div>
      <div style="position: absolute; left: 166px; bottom: -2px; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #64748b;"></div>
    </div>
  </div>

  <!-- Screening -->
  <div style="display: flex; margin-bottom: 0;">
    <div style="width: 40px; background-color: #43b09c; color: white; display: flex; align-items: center; justify-content: center; writing-mode: vertical-rl; transform: rotate(180deg); font-weight: bold; letter-spacing: 2px; padding: 10px 0; border-radius: 4px;">
      Screening
    </div>
    <div style="flex-grow: 1; padding-left: 20px; display: flex; align-items: center; position: relative; min-height: 80px;">
      <div style="border: 1px solid #64748b; padding: 15px; background: #f8fafc; width: 300px; text-align: left; border-radius: 2px; box-shadow: 2px 2px 0px rgba(0,0,0,0.05);">
        <b>{t["prisma_screened"]}</b><br/>(n = {s.get("screened", 0)})
      </div>
      <div style="width: 50px; height: 2px; background-color: #64748b; position: relative;">
        <div style="position: absolute; right: -2px; top: -4px; width: 0; height: 0; border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 6px solid #64748b;"></div>
      </div>
      <div style="border: 1px solid #64748b; padding: 15px; background: #f1f5f9; width: 250px; text-align: left; border-radius: 2px; box-shadow: 2px 2px 0px rgba(0,0,0,0.05);">
        <b>{t["prisma_excluded"]}</b><br/>(n = {s.get("excluded", 0)})
      </div>
    </div>
  </div>

  <!-- Arrow 2 -->
  <div style="display: flex; height: 30px;">
    <div style="width: 40px;"></div>
    <div style="flex-grow: 1; padding-left: 20px; position: relative;">
      <div style="position: absolute; left: 170px; top: 0; height: 100%; width: 2px; background-color: #64748b;"></div>
      <div style="position: absolute; left: 166px; bottom: -2px; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #64748b;"></div>
    </div>
  </div>

  <!-- Eligibility -->
  <div style="display: flex; margin-bottom: 0;">
    <div style="width: 40px; background-color: #43b09c; color: white; display: flex; align-items: center; justify-content: center; writing-mode: vertical-rl; transform: rotate(180deg); font-weight: bold; letter-spacing: 2px; padding: 10px 0; border-radius: 4px;">
      Eligibility
    </div>
    <div style="flex-grow: 1; padding-left: 20px; display: flex; align-items: center; position: relative; min-height: 80px;">
      <div style="border: 1px solid #64748b; padding: 15px; background: #f8fafc; width: 300px; text-align: left; border-radius: 2px; box-shadow: 2px 2px 0px rgba(0,0,0,0.05);">
        <b>{t["prisma_sought"]}</b><br/>(n = {s.get("included", 0)})
      </div>
      <div style="width: 50px; height: 2px; background-color: #64748b; position: relative;">
        <div style="position: absolute; right: -2px; top: -4px; width: 0; height: 0; border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 6px solid #64748b;"></div>
      </div>
      <div style="border: 1px solid #64748b; padding: 15px; background: #f1f5f9; width: 250px; text-align: left; border-radius: 2px; box-shadow: 2px 2px 0px rgba(0,0,0,0.05);">
        <b>원문 미확보(Not retrieved)</b><br/>(n = {s.get("included", 0) - s.get("retrieved", 0)})
      </div>
    </div>
  </div>

  <!-- Arrow 3 -->
  <div style="display: flex; height: 30px;">
    <div style="width: 40px;"></div>
    <div style="flex-grow: 1; padding-left: 20px; position: relative;">
      <div style="position: absolute; left: 170px; top: 0; height: 100%; width: 2px; background-color: #64748b;"></div>
      <div style="position: absolute; left: 166px; bottom: -2px; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #64748b;"></div>
    </div>
  </div>

  <!-- Included -->
  <div style="display: flex; margin-bottom: 0;">
    <div style="width: 40px; background-color: #43b09c; color: white; display: flex; align-items: center; justify-content: center; writing-mode: vertical-rl; transform: rotate(180deg); font-weight: bold; letter-spacing: 2px; padding: 10px 0; border-radius: 4px;">
      Included
    </div>
    <div style="flex-grow: 1; padding-left: 20px; display: flex; align-items: center; min-height: 80px;">
      <div style="border: 1px solid #64748b; padding: 15px; background: #f8fafc; width: 300px; text-align: left; border-radius: 2px; box-shadow: 2px 2px 0px rgba(0,0,0,0.05);">
        <b>{t["prisma_retrieved"]}</b><br/>(n = {s.get("retrieved", 0)})<br/><br/>
        <b>{t["prisma_included"]}</b><br/>(n = {s.get("retrieved", 0)})
      </div>
    </div>
  </div>
</div>
"""
    return mermaid_code


def _get_analyzed_pmids():
    """
    Returns the set of PMIDs that were actually analyzed (PDF retrieved and not skipped).
    This is the ground truth for what went through the analysis pipeline.
    """
    from src.utils import db_manager

    articles_df = db_manager.get_articles_df()
    if articles_df.empty:
        return set()
    if "pdf_download_status" not in articles_df.columns:
        return set(articles_df["pmid"].astype(str).tolist())

    retrieved_mask = articles_df["pdf_download_status"].astype(str).str.contains(r"Downloaded|Exists", case=False, na=False)
    return set(articles_df[retrieved_mask]["pmid"].astype(str).tolist())


def translate_dataframe(df, target_lang="KO"):
    """
    Translates all text columns in a PICO extraction DataFrame using the LLM.
    Returns a new translated DataFrame.
    """
    import json
    import re

    from src.llm import client as llm_client

    llm = llm_client.LLMClient()

    # Translate ALL text columns except pmid
    text_cols = [c for c in df.columns if c != "pmid"]

    translated_rows = []
    for _, row in df.iterrows():
        new_row = dict(row)
        texts_to_translate = {
            col: str(row[col]) for col in text_cols if pd.notna(row[col]) and str(row[col]).strip() and str(row[col]) != "nan"
        }

        if not texts_to_translate:
            translated_rows.append(new_row)
            continue

        lang_name = "Korean" if target_lang == "KO" else "English"
        prompt = f"""You MUST translate ALL of the following JSON values into {lang_name}.
Every single value must be fully translated. Do NOT leave any value in English.

Rules:
- Return ONLY a valid JSON object with the exact same keys.
- Translate EVERY value completely into {lang_name}. No exceptions.
- For proper nouns, drug names, or measurement tools (OHIP-14, SF-36, etc.), keep the original term in parentheses after the Korean translation.
  Example: "환자 보고 결과 (Patient-Reported Outcomes, PROs)"
- For direct quotes from papers, translate the quote content into {lang_name}.
- Do NOT use ** (double asterisks) anywhere.

Input:
{json.dumps(texts_to_translate, ensure_ascii=False, indent=2)}"""

        messages = [
            {
                "role": "system",
                "content": f"You are a professional medical translator specializing in dentistry and systematic reviews. You MUST translate every single value fully into {lang_name}. Leaving any English text untranslated is unacceptable.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = llm.get_completion(messages)
            if response:
                json_match = re.search(r"({[\s\S]*})", response)
                if json_match:
                    translated = json.loads(json_match.group(1))
                    for col, val in translated.items():
                        if col in new_row:
                            new_row[col] = val
        except Exception:
            pass  # Keep original text on failure

        translated_rows.append(new_row)

    return pd.DataFrame(translated_rows)


def generate_report(
    stats,
    picos,
    output_path,
    lang="EN",
    synthesis_result=None,
    run_mode="hitl",
):
    """
    Generates a comprehensive Markdown report.
    Recalculates stats from DB for accuracy.
    Filters RoB and PICO data from DB.
    """
    print(f"\n--- Generating Final Report ({lang}) ---")

    t = REPORT_TRANSLATIONS.get(lang, REPORT_TRANSLATIONS["EN"])

    # Recalculate stats from DB for accuracy
    recalculated_stats = dict(stats)
    import json

    from src.utils import db_manager

    articles_df = db_manager.get_articles_df()

    if not articles_df.empty:
        recalculated_stats["total_found"] = len(articles_df)

        # Pull duplicates stats from DB metadata
        try:
            total_dups = int(db_manager.get_meta("total_duplicates_removed", 0))
        except Exception:
            total_dups = 0

        recalculated_stats["duplicates_removed"] = total_dups
        recalculated_stats["gross_total_found"] = len(articles_df) + total_dups

        if "screening_decision" in articles_df.columns:
            screened_mask = articles_df["screening_decision"] != ""
            recalculated_stats["screened"] = int(screened_mask.sum())
            recalculated_stats["included"] = int((articles_df["screening_decision"] == "Included").sum())
            recalculated_stats["excluded"] = recalculated_stats["screened"] - recalculated_stats["included"]
        else:
            recalculated_stats["screened"] = len(articles_df)
            recalculated_stats["included"] = len(articles_df)
            recalculated_stats["excluded"] = 0

        if "pdf_download_status" in articles_df.columns:
            retrieved_mask = (
                articles_df["pdf_download_status"].astype(str).str.contains(r"Downloaded|Exists", case=False, na=False)
            )
            recalculated_stats["retrieved"] = int(retrieved_mask.sum())
        else:
            recalculated_stats["retrieved"] = recalculated_stats.get("retrieved", 0)

    s = recalculated_stats

    # Extract analyzed PMIDs from DB
    analyzed_pmids = None
    if not articles_df.empty and "pdf_download_status" in articles_df.columns:
        analyzed_mask = articles_df["pdf_download_status"].isin(
            ["Downloaded", "Already Downloaded", "Downloaded (Unpaywall)", "Downloaded (PMC)"]
        )
        analyzed_pmids = set(articles_df[analyzed_mask]["pmid"].astype(str).tolist())

    with open(output_path, "w", encoding="utf-8") as f:
        # Watermark
        if run_mode == "scoping":
            f.write("> [!WARNING]\n")
            f.write("> **SYSTEM WARNING**: This report was generated via **Full AI-driven Scoping Mode**. ")
            f.write(
                "It was NOT verified by a human expert. STRICTLY PROHIBITED for clinical guide or academic publication use.\n\n"
            )

        # Title and Header
        f.write(f"# {t['title']}\n")
        f.write(f"**{t['date']}:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        # PICO Configuration
        f.write(f"## {t['pico_header']}\n")
        if picos:
            for k, v in picos.items():
                f.write(f"- **{k.capitalize()}:** {v}\n")
        f.write("\n")

        # Synthesis
        if synthesis_result:
            f.write("## 6. 결론 및 고찰 (Synthesis)\n")
            # Strip any double asterisks just in case the LLM includes them
            clean_synthesis = synthesis_result.replace("**", "")
            f.write(clean_synthesis)
            f.write("\n\n")

        # PRISMA Flow
        f.write(f"## {t['prisma_header']}\n")
        f.write(generate_prisma_mermaid(s, lang=lang))
        f.write("\n")

        # Statistics Summary
        f.write(f"## {t['stats_header']}\n")
        f.write(f"- {t['stat_total']}: {s.get('total_found', 0)}\n")
        f.write(f"- {t['stat_screened']}: {s.get('screened', 0)}\n")
        f.write(f"- {t['stat_excluded']}: {s.get('excluded', 0)}\n")
        f.write(f"- {t['stat_included']}: {s.get('included', 0)}\n")
        f.write(f"- {t['stat_retrieved']}: {s.get('retrieved', 0)}\n")
        f.write("\n")

        # Extracted Data Summary
        f.write(f"## {t['extract_header']}\n")

        pico_records = []
        if not articles_df.empty and "pico_data" in articles_df.columns:
            for _, row in articles_df.iterrows():
                if str(row["pmid"]) in (analyzed_pmids or set()) and row["pico_data"]:
                    try:
                        pico_records.append(json.loads(row["pico_data"]))
                    except Exception:
                        pass

        if pico_records:
            df = pd.DataFrame(pico_records)
            # Translate if target language is Korean
            if lang == "KO":
                print("Translating extracted data to Korean...")
                df = translate_dataframe(df, target_lang="KO")

            f.write(f"{t['extract_count']}: {len(df)}\n\n")
            f.write(df.to_markdown(index=False))
        else:
            f.write(f"{t['no_extract']}\n")
        f.write("\n\n")

        # RoB Summary
        f.write(f"## {t['rob_header']}\n")
        rob_records = []
        if not articles_df.empty and "rob_data" in articles_df.columns:
            for _, row in articles_df.iterrows():
                if str(row["pmid"]) in (analyzed_pmids or set()) and row["rob_data"]:
                    try:
                        rob_json = json.loads(row["rob_data"])
                        # Flatten
                        flat_result = {"pmid": rob_json["pmid"]}
                        for domain, details in rob_json.items():
                            if domain == "pmid":
                                continue
                            if isinstance(details, dict):
                                flat_result[f"{domain}_Level"] = details.get("level", "Unclear")
                                quote = details.get("quote", "")
                                reasoning = details.get("reasoning", "")
                                flat_result[f"{domain}_Explanation"] = f"Quote: '{quote}' | Reasoning: {reasoning}"
                            else:
                                flat_result[domain] = str(details)
                        rob_records.append(flat_result)
                    except Exception:
                        pass

        if rob_records:
            rob_df = pd.DataFrame(rob_records)
            f.write(f"{t['rob_count'].format(count=len(rob_df))}\n\n")
            f.write(rob_df.to_markdown(index=False))
        else:
            f.write(f"{t['no_rob']}\n")
        f.write("\n")

        # References Section
        f.write("## 7. References\n")
        if not articles_df.empty and analyzed_pmids:
            ref_df = articles_df[articles_df["pmid"].astype(str).isin(analyzed_pmids)]
            if not ref_df.empty:
                for _, row in ref_df.iterrows():
                    title = row.get("title", "No Title")
                    journal = row.get("journal", "Unknown Journal")
                    year = row.get("pub_year", "n.d.")
                    pmid = row.get("pmid", "Unknown PMID")
                    f.write(f"- {title}. *{journal}* ({year}). PMID: {pmid}\n")
            else:
                f.write("No references found.\n")
        else:
            f.write("No references found.\n")
        f.write("\n")

        # Watermark Footer
        if run_mode == "scoping":
            f.write("\n---\n")
            f.write("**[⚠️ SYSTEM WARNING]** This report is an auto-generated draft using Full AI-driven Scoping Mode.\n")

    print(f"Report saved to {output_path}")
