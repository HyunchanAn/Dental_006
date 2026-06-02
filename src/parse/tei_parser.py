import os
import xml.etree.ElementTree as ET


def extract_text_from_tei(xml_path, optimize_context=True):
    """
    Parses a TEI XML file and extracts the plain text content from the body.
    If optimize_context is True, it attempts to slice only relevant sections (e.g., Methods, Results) to save LLM tokens.

    Args:
        xml_path (str): The path to the TEI XML file.
        optimize_context (bool): Whether to slice only specific sections.

    Returns:
        str: The concatenated plain text content, or an empty string if parsing fails.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Define the TEI namespace
        ns = {"tei": "http://www.tei-c.org/ns/1.0"}

        # Find the body of the text
        body = root.find(".//tei:body", ns)

        if body is None:
            return ""

        if optimize_context:
            target_keywords = [
                "method",
                "result",
                "analysis",
                "statistic",
                "measure",
                "outcome",
                "intervention",
                "design",
                "participant",
            ]
            extracted_texts = []

            for div in body.findall(".//tei:div", ns):
                head = div.find("tei:head", ns)
                if head is not None and head.text:
                    head_text = head.text.lower()
                    if any(kw in head_text for kw in target_keywords):
                        extracted_texts.append("".join(div.itertext()))

            if extracted_texts:
                text_content = " ".join(extracted_texts)
            else:
                # Fallback to full text if no matching sections are found
                text_content = "".join(body.itertext())
        else:
            # Iterate through all text nodes in the body and join them
            text_content = "".join(body.itertext())

        # Clean up excessive whitespace and newlines
        final_text = " ".join(text_content.split())

        # Cloudflare / WAF Block Detection
        lower_text = final_text.lower()
        if (
            "just a moment" in lower_text
            or "please stand by" in lower_text
            or "enable javascript and cookies" in lower_text
            or "cloudflare" in lower_text
        ):
            print(f"Warning: Blocked by Cloudflare or WAF in {xml_path}. Considering extraction failed.")
            try:
                from src.utils import db_manager

                pmid = os.path.basename(xml_path).replace(".xml", "")
                db_manager.update_article(pmid, pdf_download_status="fetch_failed")
            except Exception as e:
                print(f"Failed to update db: {e}")
            return "CLOUDFLARE_BLOCK"

        return final_text

    except ET.ParseError as e:
        print(f"Error parsing TEI XML file {xml_path}: {e}")
        return ""
    except Exception as e:
        print(f"An unexpected error occurred while processing {xml_path}: {e}")
        return ""


if __name__ == "__main__":
    # Example usage
    # Assumes there is a test file in data/tei/
    print("--- Testing TEI Parser ---")
    current_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    tei_dir = os.path.join(project_root, "data", "tei")

    test_xml_path = None
    if os.path.exists(tei_dir):
        for fname in os.listdir(tei_dir):
            if fname.lower().endswith(".xml"):
                test_xml_path = os.path.join(tei_dir, fname)
                break

    if test_xml_path:
        print(f"--- Extracting text from {os.path.basename(test_xml_path)} ---")
        text = extract_text_from_tei(test_xml_path)
        if text:
            print(text[:1000] + "...")
        else:
            print("Failed to extract text.")
    else:
        print("No TEI XML file found in data/tei/ for testing.")
