import os
import requests

# The default URL for the GROBID service started with docker-compose
GROBID_URL = "http://localhost:8090"
GROBID_API_URL = f"{GROBID_URL}/api/processFulltextDocument"

def process_pdf(pdf_path, timeout=60):
    """
    Sends a PDF file to the GROBID service to be processed and returns the TEI XML.

    Args:
        pdf_path (str): The full path to the PDF file.
        timeout (int): The timeout for the request in seconds.

    Returns:
        str: The TEI XML as a string if successful, None otherwise.
    """
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return None

    print(f"Processing {os.path.basename(pdf_path)} with GROBID...")
    try:
        with open(pdf_path, 'rb') as f:
            # Using a simpler dictionary format for the `files` parameter
            clean_filename = os.path.basename(pdf_path)
            files = {'input': (clean_filename, f, 'application/pdf')}
            
            # Make the request to the GROBID server
            response = requests.post(GROBID_API_URL, files=files, timeout=timeout)
            
            if response.status_code == 200:
                print("  - Successfully processed by GROBID.")
                return response.text
            else:
                print(f"  - Error processing with GROBID. Status: {response.status_code}, Response: {response.text[:500]}")
                return None
    except requests.exceptions.RequestException as e:
        print(f"  - GROBID service connection failed: {e}")
        print(f"    Is the GROBID service running? Try running 'start_services.bat'.")
        return None

if __name__ == '__main__':
    # This allows the script to be run directly for testing purposes.
    print("--- Testing GROBID Client ---")
    
    # Setup paths assuming the script is in src/parse
    current_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
    pdf_dir = os.path.join(project_root, 'data', 'pdf')
    tei_dir = os.path.join(project_root, 'data', 'tei')
    
    os.makedirs(tei_dir, exist_ok=True)

    # Find the first PDF in the data/pdf directory to use for the test
    test_pdf_path = None
    if os.path.exists(pdf_dir):
        for fname in os.listdir(pdf_dir):
            if fname.lower().endswith('.pdf'):
                test_pdf_path = os.path.join(pdf_dir, fname)
                break

    if not test_pdf_path:
        print("\nTest failed: No PDF found in 'data/pdf' to test with.")
        print("Please run 'python main.py' first to download some PDFs.")
    else:
        print(f"\nFound test PDF: {os.path.basename(test_pdf_path)}")
        
        # Process the PDF
        tei_xml = process_pdf(test_pdf_path)
        
        if tei_xml:
            # Save the output for inspection
            output_filename = os.path.basename(test_pdf_path).replace('.pdf', '.xml')
            output_path = os.path.join(tei_dir, output_filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(tei_xml)
            print(f"\nTest successful. Saved TEI XML output to: {output_path}")
        else:
            print("\nTest failed. Could not process the PDF.")