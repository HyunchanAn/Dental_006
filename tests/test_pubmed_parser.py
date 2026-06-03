from src.parse import pubmed_parser


def test_parse_articles_basic():
    xml_data = """<?xml version="1.0" ?>
    <PubmedArticleSet>
        <PubmedArticle>
            <MedlineCitation>
                <PMID>12345</PMID>
                <Article>
                    <ArticleTitle>Test Title</ArticleTitle>
                    <Journal>
                        <Title>Test Journal</Title>
                    </Journal>
                    <Abstract>
                        <AbstractText>Test Abstract</AbstractText>
                    </Abstract>
                </Article>
            </MedlineCitation>
            <PubmedData>
                <ArticleIdList>
                    <ArticleId IdType="doi">10.1234/test</ArticleId>
                </ArticleIdList>
            </PubmedData>
        </PubmedArticle>
    </PubmedArticleSet>
    """
    df = pubmed_parser.parse_articles(xml_data)
    assert not df.empty
    assert df.iloc[0]["pmid"] == "12345"
    assert df.iloc[0]["title"] == "Test Title"
    assert df.iloc[0]["abstract"] == "Test Abstract"
    assert df.iloc[0]["doi"] == "10.1234/test"


def test_parse_articles_deduplication_title():
    xml_data = """<?xml version="1.0" ?>
    <PubmedArticleSet>
        <PubmedArticle>
            <MedlineCitation>
                <PMID>1</PMID>
                <Article><ArticleTitle>Duplicate Title</ArticleTitle></Article>
            </MedlineCitation>
        </PubmedArticle>
        <PubmedArticle>
            <MedlineCitation>
                <PMID>2</PMID>
                <Article><ArticleTitle>Duplicate Title</ArticleTitle></Article>
            </MedlineCitation>
        </PubmedArticle>
    </PubmedArticleSet>
    """
    df = pubmed_parser.parse_articles(xml_data)
    assert len(df) == 1
    assert df.iloc[0]["pmid"] == "1"


def test_parse_articles_empty_title_not_dropped():
    xml_data = """<?xml version="1.0" ?>
    <PubmedArticleSet>
        <PubmedArticle>
            <MedlineCitation>
                <PMID>1</PMID>
                <Article><ArticleTitle></ArticleTitle></Article>
            </MedlineCitation>
        </PubmedArticle>
        <PubmedArticle>
            <MedlineCitation>
                <PMID>2</PMID>
                <Article><ArticleTitle></ArticleTitle></Article>
            </MedlineCitation>
        </PubmedArticle>
    </PubmedArticleSet>
    """
    df = pubmed_parser.parse_articles(xml_data)
    assert len(df) == 2
    assert set(df["pmid"].tolist()) == {"1", "2"}
