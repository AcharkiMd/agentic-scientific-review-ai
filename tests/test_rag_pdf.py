import io
import pytest
import fitz
from reviewai.provider import DemoProvider
from reviewai.rag import HybridRAG,chunk_text
from reviewai.pdf_ingest import extract_pdf,_public_https_url,MAX_BYTES


def test_chunks_overlap():
    chunks=chunk_text("abcdefg",chunk_size=4,overlap=1)
    assert chunks==["abcd","defg","g"]


def test_chunk_invalid_overlap():
    with pytest.raises(ValueError): chunk_text("hi",3,3)


def test_rag_persists_and_reloads(tmp_path):
    papers=[{"id":"P1","title":"Lakehouse query planning","full_text":"Large scalable lakehouse queries and cost optimization. " * 35}]
    rag=HybridRAG(tmp_path,DemoProvider())
    assert rag.build(papers)>1
    hits=rag.search("lakehouse cost optimization")
    assert hits and hits[0]["paper_id"]=="P1"
    assert all("score" in h for h in hits)
    restored=HybridRAG(tmp_path,DemoProvider())
    restored.load()
    assert restored.search("lakehouse")


def test_rag_empty_index(tmp_path):
    rag=HybridRAG(tmp_path,DemoProvider())
    assert rag.build([{"id":"x","full_text":""}])==0
    assert rag.search("hello")==[]


def test_read_actual_pdf_bytes():
    doc=fitz.open()
    page=doc.new_page()
    page.insert_text((50,50),"Scientific PDF fixture passage")
    data=doc.tobytes()
    doc.close()
    assert "Scientific PDF fixture passage" in extract_pdf(data)


def test_reject_non_pdf_and_oversize():
    with pytest.raises(ValueError):extract_pdf(b"hello")
    with pytest.raises(ValueError):extract_pdf(b"%PDF"+b"x"*MAX_BYTES)


def test_reject_internal_urls():
    assert not _public_https_url("http://example.org/p.pdf")
    assert not _public_https_url("https://127.0.0.1/p.pdf")
    assert not _public_https_url("https://user:password@example.com/p.pdf")
