from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_text_pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
    })
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 250 Td (PDF upload integration text.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_upload_rejects_unsupported_file_extension(client):
    response = client.post(
        "/api/upload",
        files={"file": ("notes.docx", b"not supported", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert "Only PDF and TXT" in response.json()["detail"]


def test_upload_rejects_empty_file(client):
    response = client.post(
        "/api/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )

    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()


def test_upload_indexes_text_and_lists_metadata(client):
    response = client.post(
        "/api/upload",
        files={"file": ("notes.txt", b"RAG retrieves relevant document passages. " * 10, "text/plain")},
    )

    assert response.status_code == 201
    uploaded = response.json()
    assert uploaded["indexed"] is True
    assert uploaded["chunk_count"] > 0
    assert uploaded["filename"] == "notes.txt"

    listed = client.get("/api/documents")
    assert listed.status_code == 200
    assert listed.json()["documents"][0]["document_id"] == uploaded["document_id"]


def test_upload_extracts_pdf_text_and_keeps_page_metadata(client):
    response = client.post(
        "/api/upload",
        files={"file": ("research.pdf", make_text_pdf(), "application/pdf")},
    )

    assert response.status_code == 201
    uploaded = response.json()
    assert uploaded["indexed"] is True
    assert uploaded["chunk_count"] > 0

    answer = client.post(
        "/api/generate",
        json={
            "question": "What text is in the PDF?",
            "document_id": uploaded["document_id"],
        },
    )

    assert answer.status_code == 200
    assert answer.json()["sources"][0]["filename"] == "research.pdf"
    assert answer.json()["sources"][0]["page_number"] == 1


def test_delete_removes_document(client, uploaded_document):
    document_id = uploaded_document["document_id"]

    response = client.delete(f"/api/documents/{document_id}")

    assert response.status_code == 200
    assert response.json() == {"document_id": document_id, "deleted": True}
    assert client.get("/api/documents").json()["documents"] == []


def test_upload_rejects_unreadable_utf8_text(client):
    response = client.post(
        "/api/upload",
        files={"file": ("bad.txt", b"\xff\xfe", "text/plain")},
    )

    assert response.status_code == 422
    assert "UTF-8" in response.json()["detail"]


def test_upload_rejects_invalid_pdf(client):
    response = client.post(
        "/api/upload",
        files={"file": ("broken.pdf", b"not a PDF file", "application/pdf")},
    )

    assert response.status_code == 422
    assert "PDF" in response.json()["detail"]


def test_chunking_keeps_expected_overlap_and_pdf_page_metadata():
    chunks = split_text("abcdefghij", size=6, overlap=2, page_number=4)

    assert [chunk.content for chunk in chunks] == ["abcdef", "efghij"]
    assert all(chunk.page_number == 4 for chunk in chunks)


def test_text_stream_chunking_handles_long_text_without_losing_content():
    source = "abcdefghij"
    chunks = split_stream(StringIO(source), size=6, overlap=2)

    assert [chunk.content for chunk in chunks] == ["abcdef", "efghij"]
    assert all(chunk.page_number is None for chunk in chunks)

from io import StringIO

from app.services.document_service import split_stream, split_text
