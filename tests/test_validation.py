from src.ingest.downloader import is_valid_html_text, is_valid_pdf


def test_is_valid_pdf_size(tmp_path):
    stub_pdf = tmp_path / "stub.pdf"
    # Create a small file < 5KB
    stub_pdf.write_bytes(b"%PDF-1.4\n" + b"A" * 1024)
    assert not is_valid_pdf(str(stub_pdf))


def test_is_valid_pdf_magic(tmp_path):
    fake_pdf = tmp_path / "fake.pdf"
    # Create a file > 5KB but no %PDF
    fake_pdf.write_bytes(b"NOTPDF" + b"A" * 6000)
    assert not is_valid_pdf(str(fake_pdf))


def test_is_valid_pdf_stub_text(tmp_path):
    paywall_pdf = tmp_path / "paywall.pdf"
    # Create a file > 5KB, with %PDF but containing redirecting
    paywall_pdf.write_bytes(b"%PDF-1.4\nRedirecting..." + b"A" * 6000)
    assert not is_valid_pdf(str(paywall_pdf))


def test_is_valid_pdf_success(tmp_path):
    valid_pdf = tmp_path / "valid.pdf"
    # Create a valid file > 5KB
    valid_pdf.write_bytes(b"%PDF-1.4\nValid content here." + b"A" * 6000)
    assert is_valid_pdf(str(valid_pdf))


def test_is_valid_html_text():
    # Test length < 500
    assert not is_valid_html_text("A" * 499)

    # Test valid text > 500
    assert is_valid_html_text("Valid science text. " + "A" * 500)

    # Test anti-bot keywords > 500
    assert not is_valid_html_text("Please wait, redirecting... " + "A" * 500)
    assert not is_valid_html_text("cloudflare check " + "A" * 500)
