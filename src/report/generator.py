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

    mermaid_code = f"""
```mermaid
graph TD
    A["{t['prisma_id']}<br/>(n = {s.get('total_found', 0)})"] --> B["{t['prisma_screened']}<br/>(n = {s.get('screened', 0)})"]
    B --> C["{t['prisma_excluded']}<br/>(n = {s.get('excluded', 0)})"]
    B --> D["{t['prisma_sought']}<br/>(n = {s.get('included', 0)})"]
    D --> E["{t['prisma_not_retrieved']}<br/>(n = {s.get('included', 0) - s.get('retrieved', 0)})"]
    D --> F["{t['prisma_retrieved']}<br/>(n = {s.get('retrieved', 0)})"]
    F --> G["{t['prisma_included']}<br/>(n = {s.get('retrieved', 0)})"]
```
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
):
    """
    Generates a comprehensive Markdown report.
    """
    print(f"\n--- Generating Final Report ({lang}) ---")

    t = REPORT_TRANSLATIONS.get(lang, REPORT_TRANSLATIONS["EN"])

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
        f.write(generate_prisma_mermaid(stats, lang=lang))
        f.write("\n")

        # Statistics Summary
        f.write(f"## {t['stats_header']}\n")
        f.write(f"- {t['stat_total']}: {stats.get('total_found', 0)}\n")
        f.write(f"- {t['stat_screened']}: {stats.get('screened', 0)}\n")
        f.write(f"- {t['stat_excluded']}: {stats.get('excluded', 0)}\n")
        f.write(f"- {t['stat_included']}: {stats.get('included', 0)}\n")
        f.write(f"- {t['stat_retrieved']}: {stats.get('retrieved', 0)}\n")
        f.write("\n")

        # Extracted Data Summary
        f.write(f"## {t['extract_header']}\n")
        if os.path.exists(extracted_csv_path):
            df = pd.read_csv(extracted_csv_path)
            f.write(f"{t['extract_count']}: {len(df)}\n\n")
            f.write(df.to_markdown(index=False))
        else:
            f.write(f"{t['no_extract']}\n")
        f.write("\n\n")

        # RoB Summary
        f.write(f"## {t['rob_header']}\n")
        if os.path.exists(rob_csv_path):
            rob_df = pd.read_csv(rob_csv_path)
            f.write(f"{t['rob_count'].format(count=len(rob_df))}\n\n")
            f.write(rob_df.to_markdown(index=False))
        else:
            f.write(f"{t['no_rob']}\n")
        f.write("\n")

    print(f"Report saved to {output_path}")
