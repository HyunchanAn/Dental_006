import pandas as pd
from src.ingest.deduplicator import deduplicate_records, normalize_title, normalize_author

def test_normalization():
    assert normalize_title("Hello, World! 2023") == "helloworld2023"
    assert normalize_title("A Study on P.C.O.S.") == "astudyonpcos"
    assert normalize_author("Smith, J.D.") == "smithjd"
    assert normalize_author("Doe") == "doe"

def test_deduplicate_doi():
    existing = pd.DataFrame([{"doi": "10.123/456", "title": "A", "first_author": "B", "pub_year": "2020"}])
    new = pd.DataFrame([{"doi": "10.123/456", "title": "C", "first_author": "D", "pub_year": "2021"}])
    res, stats = deduplicate_records(existing, new)
    assert stats["duplicates_removed"] == 1
    assert len(res) == 0

def test_deduplicate_title():
    existing = pd.DataFrame([{"doi": "", "title": "Hello, World!", "first_author": "B", "pub_year": "2020"}])
    new = pd.DataFrame([{"doi": "", "title": "hello world", "first_author": "D", "pub_year": "2021"}])
    res, stats = deduplicate_records(existing, new)
    assert stats["duplicates_removed"] == 1
    assert len(res) == 0

def test_deduplicate_cross():
    existing = pd.DataFrame([{"doi": "", "title": "Long title that is similar enough to match 20 chars", "first_author": "Smith, J", "pub_year": "2020"}])
    new = pd.DataFrame([{"doi": "", "title": "Long title that is similar enough to match extra words", "first_author": "Smith", "pub_year": "2020"}])
    res, stats = deduplicate_records(existing, new)
    assert stats["duplicates_removed"] == 1
    assert len(res) == 0

def test_no_duplicates():
    existing = pd.DataFrame([{"doi": "10.1", "title": "Title 1", "first_author": "A", "pub_year": "2020"}])
    new = pd.DataFrame([{"doi": "10.2", "title": "Title 2", "first_author": "B", "pub_year": "2021"}])
    res, stats = deduplicate_records(existing, new)
    assert stats["duplicates_removed"] == 0
    assert len(res) == 1
