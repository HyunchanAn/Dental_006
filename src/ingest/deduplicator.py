import re

import pandas as pd


def normalize_title(title):
    """Removes punctuation and extra spaces, converts to lowercase."""
    if not isinstance(title, str):
        return ""
    # Remove everything except alphanumeric (including spaces)
    return re.sub(r"[^\w]", "", title.lower())


def normalize_author(author):
    """Extracts last name or removes spaces/punctuation for comparison."""
    if not isinstance(author, str):
        return ""
    # Extract last name (before comma) to improve matching, then remove non-alphanumeric
    last_name = author.split(",")[0]
    return re.sub(r"[^\w]", "", last_name.lower())


def deduplicate_records(existing_df, new_df):
    """
    Deduplicates new_df against existing_df.
    Priority: pubmed > embase > cochrane > external (implicitly handled by keeping existing)
    Returns:
        deduped_new_df: DataFrame of purely new records to be inserted.
        stats: dict with duplicate counts
    """
    if new_df.empty:
        return new_df, {"total_uploaded": 0, "duplicates_removed": 0, "new_records": 0}

    total_uploaded = len(new_df)

    # 1. Prepare normalized columns for both dataframes
    if not existing_df.empty:
        existing_df["norm_title"] = existing_df["title"].apply(normalize_title)
        existing_df["norm_author"] = existing_df["first_author"].apply(normalize_author)
    else:
        existing_df = pd.DataFrame(columns=new_df.columns.tolist() + ["norm_title", "norm_author"])

    new_df["norm_title"] = new_df["title"].apply(normalize_title)
    new_df["norm_author"] = new_df["first_author"].apply(normalize_author)

    # First, internally deduplicate new_df by pmid (if present) and norm_title
    if "pmid" in new_df.columns:
        non_empty_pmid = new_df["pmid"].astype(str).str.strip().replace("nan", "")
        has_pmid_mask = non_empty_pmid != ""
        with_pmid = new_df[has_pmid_mask].drop_duplicates(subset=["pmid"])
        without_pmid = new_df[~has_pmid_mask]
        new_df = pd.concat([with_pmid, without_pmid], ignore_index=True)
    new_df = new_df.drop_duplicates(subset=["norm_title"])

    duplicates_removed = total_uploaded - len(new_df)

    existing_pmids = set()
    if "pmid" in existing_df.columns and not existing_df.empty:
        existing_pmids = {
            str(v).strip()
            for v in existing_df["pmid"].tolist()
            if v is not None and str(v).strip() and str(v).strip().lower() != "nan"
        }

    records_to_keep = []

    for _, new_row in new_df.iterrows():
        is_duplicate = False

        # 0. PMID Exact Match (PubMed + PubTator 3.0 supplemental merge safety)
        cand_pmid = str(new_row.get("pmid", "")).strip() if "pmid" in new_row else ""
        if cand_pmid and cand_pmid.lower() != "nan" and cand_pmid in existing_pmids:
            is_duplicate = True

        # 1. DOI Match
        if new_row["doi"] and str(new_row["doi"]).strip() and str(new_row["doi"]).lower() != "nan":
            doi_matches = existing_df[existing_df["doi"] == new_row["doi"]]
            if not doi_matches.empty:
                is_duplicate = True

        # 2. Exact Title Match (Normalized)
        if not is_duplicate and new_row["norm_title"]:
            title_matches = existing_df[existing_df["norm_title"] == new_row["norm_title"]]
            if not title_matches.empty:
                is_duplicate = True

        # 3. Cross Validation Match (Title 1st pass + Year + Author)
        if not is_duplicate and new_row["norm_title"] and new_row["pub_year"] and new_row["norm_author"]:
            # Let's say title starts with the same 20 chars
            short_title = new_row["norm_title"][:20]
            cross_matches = existing_df[
                (existing_df["norm_title"].str.startswith(short_title, na=False))
                & (existing_df["pub_year"] == new_row["pub_year"])
                & (existing_df["norm_author"] == new_row["norm_author"])
            ]
            if not cross_matches.empty:
                is_duplicate = True

        if not is_duplicate:
            records_to_keep.append(new_row)
        else:
            duplicates_removed += 1
            # Note: We drop the new record entirely, keeping the existing one (e.g. PubMed) as Master.

    deduped_df = pd.DataFrame(records_to_keep)
    if "norm_title" in deduped_df.columns:
        deduped_df = deduped_df.drop(columns=["norm_title", "norm_author"])

    stats = {
        "total_uploaded": total_uploaded,
        "duplicates_removed": duplicates_removed,
        "new_records": len(deduped_df),
    }

    return deduped_df, stats
