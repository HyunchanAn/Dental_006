import os
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
        <b>{t['prisma_id']}</b><br/>(n = {s.get('total_found', 0)})
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
        <b>{t['prisma_screened']}</b><br/>(n = {s.get('screened', 0)})
      </div>
      <div style="width: 50px; height: 2px; background-color: #64748b; position: relative;">
        <div style="position: absolute; right: -2px; top: -4px; width: 0; height: 0; border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 6px solid #64748b;"></div>
      </div>
      <div style="border: 1px solid #64748b; padding: 15px; background: #f1f5f9; width: 250px; text-align: left; border-radius: 2px; box-shadow: 2px 2px 0px rgba(0,0,0,0.05);">
        <b>{t['prisma_excluded']}</b><br/>(n = {s.get('excluded', 0)})
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
        <b>{t['prisma_sought']}</b><br/>(n = {s.get('included', 0)})
      </div>
      <div style="width: 50px; height: 2px; background-color: #64748b; position: relative;">
        <div style="position: absolute; right: -2px; top: -4px; width: 0; height: 0; border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 6px solid #64748b;"></div>
      </div>
      <div style="border: 1px solid #64748b; padding: 15px; background: #f1f5f9; width: 250px; text-align: left; border-radius: 2px; box-shadow: 2px 2px 0px rgba(0,0,0,0.05);">
        <b>원문 미확보(Not retrieved)</b><br/>(n = {s.get('included', 0) - s.get('retrieved', 0)})
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
        <b>{t['prisma_retrieved']}</b><br/>(n = {s.get('retrieved', 0)})<br/><br/>
        <b>{t['prisma_included']}</b><br/>(n = {s.get('retrieved', 0)})
      </div>
    </div>
  </div>
</div>
"""
    return mermaid_code


def generate_report(
    stats,
    picos,
    extracted_csv_path,
    rob_csv_path,
    output_path,
    lang="EN",
    synthesis_result=None,
    articles_csv_path=None,
):
    """
    Generates a comprehensive Markdown report.
    Recalculates stats from actual CSV data for accuracy.
    """
    print(f"\n--- Generating Final Report ({lang}) ---")

    t = REPORT_TRANSLATIONS.get(lang, REPORT_TRANSLATIONS["EN"])

    # Recalculate stats from actual CSV data for accuracy
    recalculated_stats = dict(stats)  # start with passed-in stats as fallback
    
    if articles_csv_path and os.path.exists(articles_csv_path):
        articles_df = pd.read_csv(articles_csv_path)
        recalculated_stats["total_found"] = len(articles_df)
        
        if "screening_decision" in articles_df.columns:
            screened_mask = articles_df["screening_decision"].notna()
            recalculated_stats["screened"] = int(screened_mask.sum())
            recalculated_stats["included"] = int(
                (articles_df["screening_decision"] == "Included").sum()
            )
            recalculated_stats["excluded"] = (
                recalculated_stats["screened"] - recalculated_stats["included"]
            )
        else:
            recalculated_stats["screened"] = len(articles_df)
            recalculated_stats["included"] = len(articles_df)
            recalculated_stats["excluded"] = 0

        if "pdf_download_status" in articles_df.columns:
            retrieved_mask = (
                articles_df["pdf_download_status"]
                .astype(str)
                .str.contains(r"Downloaded|Exists", case=False, na=False)
            )
            recalculated_stats["retrieved"] = int(retrieved_mask.sum())
        else:
            recalculated_stats["retrieved"] = recalculated_stats.get("retrieved", 0)

    s = recalculated_stats

    with open(output_path, "w", encoding="utf-8") as f:
        # Title and Header
        f.write(f"# {t['title']}\n")
        f.write(f"**{t['date']}:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        # PICO Configuration
        f.write(f"## {t['pico_header']}\n")
        if picos:
            for k, v in picos.items():
                f.write(f"- **{k.capitalize()}:** {v}\n")
        f.write("\n")

        # Synthesis (New Section)
        if synthesis_result:
            f.write("## 6. 결론 및 고찰 (Synthesis)\n")
            f.write(synthesis_result)
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
        if os.path.exists(extracted_csv_path):
            df = pd.read_csv(extracted_csv_path)
            # Filter to only include PMIDs that are actually in the current project
            if articles_csv_path and os.path.exists(articles_csv_path):
                valid_pmids = set(
                    pd.read_csv(articles_csv_path)["pmid"].astype(str).tolist()
                )
                df["pmid"] = df["pmid"].astype(str)
                df = df[df["pmid"].isin(valid_pmids)]
            f.write(f"{t['extract_count']}: {len(df)}\n\n")
            f.write(df.to_markdown(index=False))
        else:
            f.write(f"{t['no_extract']}\n")
        f.write("\n\n")

        # RoB Summary
        f.write(f"## {t['rob_header']}\n")
        if os.path.exists(rob_csv_path):
            rob_df = pd.read_csv(rob_csv_path)
            # Filter to only include PMIDs that are actually in the current project
            if articles_csv_path and os.path.exists(articles_csv_path):
                valid_pmids = set(
                    pd.read_csv(articles_csv_path)["pmid"].astype(str).tolist()
                )
                rob_df["pmid"] = rob_df["pmid"].astype(str)
                rob_df = rob_df[rob_df["pmid"].isin(valid_pmids)]
            f.write(f"{t['rob_count'].format(count=len(rob_df))}\n\n")
            f.write(rob_df.to_markdown(index=False))
        else:
            f.write(f"{t['no_rob']}\n")
        f.write("\n")

    print(f"Report saved to {output_path}")

