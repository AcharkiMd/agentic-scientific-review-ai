import pytest
from reviewai.sources import reconstruct_abstract,clean_doi,normalize_title,deduplicate,normalize_paper,AcademicSources


def test_reconstruct_abstract():
    assert reconstruct_abstract({"this":[0],"works":[1],"well":[2]}) == "this works well"
    assert reconstruct_abstract({}) == ""
    assert reconstruct_abstract({"x":[999999]}) == ""


def test_doi_normalization():
    assert clean_doi("HTTPS://DOI.ORG/10.1/ABC") == "10.1/abc"
    assert clean_doi("doi:10.2/FOO") == "10.2/foo"


def test_title_normalization():
    assert normalize_title("Étude:  Lakehouse,  Query!") == "etude lakehouse query"


def test_dedup_retains_provenance():
    a={"id":"a","title":"Amazing Paper","year":2024,"source":"OpenAlex","abstract":"short"}
    b={"id":"b","title":"Amazing paper!","year":2024,"source":"arXiv","abstract":"longer abstract"}
    papers,removed=deduplicate([a,b])
    assert removed==1
    assert len(papers)==1
    assert papers[0]["sources"]==["OpenAlex","arXiv"]
    assert papers[0]["abstract"]=="longer abstract"


def test_dedup_doi_across_renamed_titles():
    a={"id":"a","title":"First title","doi":"https://doi.org/10.555/a","source":"OpenAlex"}
    b={"id":"b","title":"Second title","doi":"10.555/A","source":"arXiv"}
    unique,removed=deduplicate([a,b])
    assert removed==1 and len(unique)==1


class FakeResponse:
    content=b""
    def __init__(self,payload):
        self.payload=payload
    def raise_for_status(self):pass
    def json(self):return self.payload

class FakeSession:
    def __init__(self):self.headers={}
    def get(self,url,params=None,timeout=None):
        if "openalex" in url:
            return FakeResponse({"results":[{"id":"W1","title":"On lakehouses", "doi":"https://doi.org/10.123/lake",
                                             "publication_year":2025,
                                             "abstract_inverted_index":{"Good":[0],"paper":[1]},
                                             "authorships":[{"author":{"display_name":"Researcher"}}],
                                             "best_oa_location":{"pdf_url":"https://example.org/p.pdf"}}]})
        return FakeResponse({"results":[]})


def test_openalex_parsing_offline():
    source=AcademicSources(session=FakeSession())
    rows=source.openalex("lakehouses",5)
    assert rows[0]["abstract"]=="Good paper"
    assert rows[0]["authors"]==["Researcher"]
    assert rows[0]["pdf_url"]=="https://example.org/p.pdf"


def test_arxiv_parsing_offline():
    class XMLSession(FakeSession):
        def get(self,*args,**kwargs):
            x=FakeResponse({})
            x.content=b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
            <id>https://arxiv.org/abs/2601.00001</id><title>Distributed Systems</title>
            <summary>A study of large data.</summary><published>2026-01-04T00:00:00Z</published>
            <author><name>Example Author</name></author>
            <link title="pdf" href="https://arxiv.org/pdf/2601.00001"/></entry></feed>'''
            return x
    rows=AcademicSources(session=XMLSession()).arxiv("distributed",5)
    assert len(rows)==1 and rows[0]["year"]==2026
    assert rows[0]["pdf_url"].endswith("2601.00001")


def test_partial_source_failure_logged():
    class BrokenArxiv(FakeSession):
        def get(self,url,params=None,timeout=None):
            if "arxiv" in url:
                import requests
                raise requests.ConnectionError("temporary failure")
            return super().get(url,params,timeout)
    papers,events=AcademicSources(session=BrokenArxiv()).search(["lakehouse"],max_papers=2)
    assert len(papers)==1
    assert any(e["status"]=="failed" for e in events)
