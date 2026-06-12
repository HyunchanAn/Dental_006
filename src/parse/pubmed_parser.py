import xml.etree.ElementTree as ET

import pandas as pd


def parse_articles(xml_string):
    """
    Parses the XML content from PubMed and returns a Pandas DataFrame.

    Args:
        xml_string (str): The raw XML string fetched from PubMed.
    """
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        print(f"Error: Failed to parse XML string. {e}")
        return

    articles_list = []
    for article in root.findall(".//PubmedArticle"):
        article_data = {}

        # Extract PMID
        pmid_node = article.find(".//PMID")
        article_data["pmid"] = pmid_node.text if pmid_node is not None else ""

        # Extract DOI
        doi_node = article.find(".//ArticleId[@IdType='doi']")
        if doi_node is None:
            doi_node = article.find(".//ELocationID[@EIdType='doi']")
        article_data["doi"] = doi_node.text if doi_node is not None else ""

        # Extract Title
        title_node = article.find(".//ArticleTitle")
        article_data["title"] = title_node.text if title_node is not None else ""

        # Extract Journal Title (Use MedlineTA abbreviation for Vancouver style)
        medline_ta_node = article.find(".//MedlineJournalInfo/MedlineTA")
        if medline_ta_node is not None and medline_ta_node.text:
            article_data["journal"] = medline_ta_node.text
        else:
            journal_title_node = article.find(".//Journal/Title")
            article_data["journal"] = journal_title_node.text if journal_title_node is not None else ""

        # Extract Authors
        authors = []
        for author in article.findall(".//AuthorList/Author"):
            last_name = author.find("LastName")
            initials = author.find("Initials")
            if last_name is not None and last_name.text:
                name = last_name.text
                if initials is not None and initials.text:
                    name += f" {initials.text}"
                authors.append(name)

        if len(authors) > 6:
            article_data["authors"] = ", ".join(authors[:6]) + ", et al."
        else:
            article_data["authors"] = ", ".join(authors)

        # Extract Volume, Issue, Pages
        vol_node = article.find(".//JournalIssue/Volume")
        article_data["volume"] = vol_node.text if vol_node is not None else ""

        issue_node = article.find(".//JournalIssue/Issue")
        article_data["issue"] = issue_node.text if issue_node is not None else ""

        pages_node = article.find(".//Pagination/MedlinePgn")
        article_data["pages"] = pages_node.text if pages_node is not None else ""

        # Extract Publication Year
        pub_year_node = article.find(".//PubDate/Year")
        article_data["pub_year"] = pub_year_node.text if pub_year_node is not None else ""

        # Extract Abstract
        abstract_nodes = article.findall(".//Abstract/AbstractText")
        abstract_text = " ".join([node.text for node in abstract_nodes if node.text])
        article_data["abstract"] = abstract_text

        articles_list.append(article_data)

    if not articles_list:
        print("No articles found in the XML to process.")
        return

    # Create DataFrame
    df = pd.DataFrame(articles_list)

    # --- Deduplication Logic ---
    initial_count = len(df)

    # 1. Deduplicate by PMID (Primary)
    df = df.drop_duplicates(subset=["pmid"], keep="first")

    # 2. Deduplicate by DOI (if exists)
    # Filter rows with DOI, deduplicate them, then merge back with rows without DOI
    has_doi = df[df["doi"] != ""].copy()
    no_doi = df[df["doi"] == ""].copy()
    has_doi = has_doi.drop_duplicates(subset=["doi"], keep="first")
    df = pd.concat([has_doi, no_doi])

    # 3. Deduplicate by Title (Normalized)
    def normalize_title(title):
        if not title:
            return ""
        import re

        # Lowercase, remove non-alphanumeric, remove extra whitespace
        return re.sub(r"[^a-zA-Z0-9]", "", title.lower())

    df["normalized_title"] = df["title"].apply(normalize_title)
    has_title = df[df["normalized_title"] != ""].copy()
    no_title = df[df["normalized_title"] == ""].copy()
    has_title = has_title.drop_duplicates(subset=["normalized_title"], keep="first")
    df = pd.concat([has_title, no_title])
    df = df.drop(columns=["normalized_title"])

    final_count = len(df)
    if initial_count > final_count:
        print(f"Deduplication: Removed {initial_count - final_count} duplicate articles. ({initial_count} -> {final_count})")

    print(f"Successfully parsed {len(df)} articles.")
    return df
