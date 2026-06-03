import os

import pandas as pd
import pytest

from src.utils import db_manager

# Override DB path for testing
TEST_DB_PATH = "data/test_systematic_reviewer.db"


@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup
    if hasattr(db_manager._local, "conn"):
        delattr(db_manager._local, "conn")
    db_manager.DB_PATH = TEST_DB_PATH
    db_manager.init_db()
    yield
    # Teardown
    if hasattr(db_manager._local, "conn"):
        db_manager._local.conn.close()
        delattr(db_manager._local, "conn")
    db_manager.clear_db()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except PermissionError:
            pass


def test_init_db():
    assert os.path.exists(TEST_DB_PATH)


def test_import_pubmed_results():
    data = {
        "pmid": ["1", "2"],
        "doi": ["10.1/1", "10.1/2"],
        "title": ["Title 1", "Title 2"],
        "journal": ["Journal 1", "Journal 2"],
        "pub_year": [2021, 2022],
        "abstract": ["Abs 1", "Abs 2"],
    }
    df = pd.DataFrame(data)
    db_manager.import_pubmed_results(df)

    db_df = db_manager.get_articles_df()
    assert len(db_df) == 2
    assert "Title 1" in db_df["title"].values


def test_update_article():
    data = {"pmid": ["1"], "title": ["Title 1"]}
    df = pd.DataFrame(data)
    db_manager.import_pubmed_results(df)

    db_manager.update_article("1", screening_decision="Included", pdf_download_status="Downloaded")

    article = db_manager.get_article("1")
    assert article["screening_decision"] == "Included"
    assert article["pdf_download_status"] == "Downloaded"
