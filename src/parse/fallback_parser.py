import re

import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_path):
    """
    Fallback parser using PyMuPDF (fitz).
    Extracts raw text from the PDF when GROBID fails.
    Returns a dummy TEI-like XML string to keep the pipeline compatible,
    or just returns the raw text wrapped in a simple XML structure.
    """
    try:
        doc = fitz.open(pdf_path)
        text_content = []
        for page in doc:
            text = page.get_text("text")
            text_content.append(text)

        full_text = "\n".join(text_content)

        # Clean up null bytes and weird chars
        full_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]", "", full_text)

        # Create a dummy TEI structure so tei_parser doesn't crash completely,
        # or we can just pass the raw text into a standard TEI format.
        # Actually, let's build a minimal valid TEI XML.
        xml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xml:space="preserve" xmlns="http://www.tei-c.org/ns/1.0"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://www.tei-c.org/ns/1.0 /grobid/schemas/tei/tei.xsd">
    <teiHeader/>
    <text>
        <body>
            <div>
                <p>{full_text}</p>
            </div>
        </body>
    </text>
</TEI>"""
        return xml_template
    except Exception as e:
        print(f"Fallback parser failed for {pdf_path}: {e}")
        return None
