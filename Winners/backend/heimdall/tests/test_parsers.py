"""Unit tests for PDF, DOCX, and TXT document parsers and ParserFactory."""

from heimdall.parsers.parser_factory import ParserFactory
from heimdall.parsers.pdf_parser import PDFParser
from heimdall.parsers.docx_parser import DocxParser
from heimdall.parsers.txt_parser import TxtParser
from heimdall.extraction.manifest_service import ManifestService
from heimdall.models.document import DocumentFormat


def test_pdf_parser_on_real_atlas_pdf():
    """Verify PyMuPDF parses ATL-0001.pdf with page numbers and paragraph indices."""
    service = ManifestService()
    path = service.get_document_file_path("ATL-0001")
    assert path is not None and path.exists()

    parser = PDFParser()
    parsed = parser.parse(file_path=path, doc_id="ATL-0001", manifest_meta=service.get_document("ATL-0001"))

    assert parsed.format == DocumentFormat.PDF
    assert parsed.total_pages is not None and parsed.total_pages >= 1
    assert parsed.total_paragraphs > 0
    assert len(parsed.paragraphs) == parsed.total_paragraphs

    # Verify first paragraph
    first_p = parsed.paragraphs[0]
    assert first_p.paragraph_index == 1
    assert first_p.page_number == 1
    assert len(first_p.raw_text) > 0

    # Verify citation formatting
    citation = parsed.make_citation(1)
    assert citation.doc_id == "ATL-0001"
    assert citation.page_number == 1
    assert citation.paragraph_index == 1
    assert citation.to_citation_str() == "[ATL-0001 p.1 ¶1]"


def test_txt_parser_on_real_atlas_txt():
    """Verify TxtParser parses ATL-0002.txt with paragraph indices."""
    service = ManifestService()
    path = service.get_document_file_path("ATL-0002")
    assert path is not None and path.exists()

    parser = TxtParser()
    parsed = parser.parse(file_path=path, doc_id="ATL-0002", manifest_meta=service.get_document("ATL-0002"))

    assert parsed.format == DocumentFormat.TXT
    assert parsed.total_paragraphs > 0
    assert len(parsed.paragraphs) == parsed.total_paragraphs

    # Verify paragraph indices are continuous 1..N
    for i, p in enumerate(parsed.paragraphs, start=1):
        assert p.paragraph_index == i

    citation = parsed.make_citation(1)
    assert citation.to_citation_str() == "[ATL-0002 ¶1]"


def test_docx_parser_on_real_atlas_docx():
    """Verify DocxParser parses ATL-0003.docx with paragraph structure."""
    service = ManifestService()
    path = service.get_document_file_path("ATL-0003")
    assert path is not None and path.exists()

    parser = DocxParser()
    parsed = parser.parse(file_path=path, doc_id="ATL-0003", manifest_meta=service.get_document("ATL-0003"))

    assert parsed.format == DocumentFormat.DOCX
    assert parsed.total_paragraphs > 0
    assert len(parsed.paragraphs) == parsed.total_paragraphs

    citation = parsed.make_citation(2)
    assert citation.to_citation_str() == "[ATL-0003 ¶2]"


def test_parser_factory_auto_dispatch():
    """Verify ParserFactory correctly resolves and parses different formats by DOC_ID."""
    factory = ParserFactory()
    
    # Test dispatch on PDF
    doc_pdf = factory.parse_by_doc_id("ORV-0001")
    assert doc_pdf.doc_id == "ORV-0001"
    assert doc_pdf.total_paragraphs > 0

    # Test dispatch on TXT
    doc_txt = factory.parse_by_doc_id("ORV-0034")
    assert doc_txt.doc_id == "ORV-0034"
    assert doc_txt.format == DocumentFormat.TXT
    assert doc_txt.total_paragraphs > 0
