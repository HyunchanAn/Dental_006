import re
import uuid

import pandas as pd


def parse_ris(file_content, source_db="external"):
    """
    A simple RIS parser without external dependencies.
    Maps to standard columns: id, pmid, source_db, doi, title, journal, pub_year, first_author, abstract
    """
    records = []
    current_record = {}

    lines = file_content.splitlines()
    for line in lines:
        if not line.strip():
            continue

        match = re.match(r"^([A-Z0-9]{2})\s+-\s+(.*)$", line)
        if match:
            tag, value = match.groups()
            value = value.strip()

            if tag == "ER":
                if current_record:
                    records.append(current_record)
                current_record = {}
            else:
                if tag in current_record:
                    current_record[tag] += " " + value
                else:
                    current_record[tag] = value

    # Map to dataframe
    mapped_records = []
    for rec in records:
        mapped = {
            "id": str(uuid.uuid4()),
            "source_db": source_db,
            "title": rec.get("TI", rec.get("T1", "")),
            "abstract": rec.get("AB", ""),
            "doi": rec.get("DO", ""),
            "journal": rec.get("JO", rec.get("T2", "")),
            "pub_year": rec.get("PY", rec.get("Y1", "")),
            "first_author": rec.get("AU", "").split(" ")[0] if rec.get("AU") else "",
            "pmid": "",  # Will be filled if we parse it out of notes, but mostly empty
        }

        # Sometimes year is like "2023/10/01", we just want "2023"
        if mapped["pub_year"]:
            year_match = re.search(r"\b(19|20)\d{2}\b", mapped["pub_year"])
            if year_match:
                mapped["pub_year"] = year_match.group(0)

        mapped_records.append(mapped)

    return pd.DataFrame(mapped_records)


def parse_csv(file_stream, source_db="external"):
    """
    Parses a CSV/TSV file using pandas and attempts to map columns.
    """
    # Try reading as CSV first, if fails try TSV
    try:
        df = pd.read_csv(file_stream)
    except Exception:
        file_stream.seek(0)
        df = pd.read_csv(file_stream, sep="\t")

    # Map common column names
    col_mapping = {
        "Title": "title",
        "Article Title": "title",
        "Abstract": "abstract",
        "DOI": "doi",
        "Journal": "journal",
        "Journal/Book": "journal",
        "Publication Year": "pub_year",
        "Year": "pub_year",
        "Author": "first_author",
        "Authors": "first_author",
        "PMID": "pmid",
    }

    # rename columns ignoring case
    df.columns = [str(c).strip() for c in df.columns]
    for orig_col in df.columns:
        for map_key, map_val in col_mapping.items():
            if orig_col.lower() == map_key.lower():
                df.rename(columns={orig_col: map_val}, inplace=True)

    # Ensure required columns exist
    for required in ["title", "abstract", "doi", "journal", "pub_year", "first_author", "pmid"]:
        if required not in df.columns:
            df[required] = ""

    # Clean up first author (take just the first one if it's a comma separated list)
    df["first_author"] = df["first_author"].astype(str).apply(lambda x: x.split(",")[0].strip() if x else "")

    df["id"] = [str(uuid.uuid4()) for _ in range(len(df))]
    df["source_db"] = source_db

    # Return only the mapped columns
    return df[["id", "pmid", "source_db", "doi", "title", "journal", "pub_year", "first_author", "abstract"]]
