import os

# Define file paths (these should ideally be passed or imported from a central config)
# For now, let's define them here for self-containment, assuming project root context
DATA_DIR = "data"
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
TABLES_DIR = os.path.join(DATA_DIR, "tables")
PDF_DIR = os.path.join(DATA_DIR, "pdf")
TEI_DIR = os.path.join(DATA_DIR, "tei")
LOGS_DIR = os.path.join(DATA_DIR, "logs")

def clear_generated_data_files():
    """
    Deletes specific generated data files and contents of the PDF directory,
    preserving directory structure and non-generated files like readme.md.
    """
    print("이전 데이터를 삭제합니다...")
    files_to_delete = [
        os.path.join(RAW_DATA_DIR, "articles.xml"),
    ]

    for f in files_to_delete:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f" - 삭제됨: {f}")
            except Exception as e:
                print(f"오류: {f} 삭제 실패. {e}")

    dirs_to_clear = [PDF_DIR, TEI_DIR, LOGS_DIR]

    for d in dirs_to_clear:
        if os.path.exists(d):
            for item in os.listdir(d):
                item_path = os.path.join(d, item)
                if os.path.isfile(item_path):  # Delete all files in these directories
                    try:
                        os.remove(item_path)
                        print(f" - 삭제됨: {item_path}")
                    except Exception as e:
                        print(f"오류: {item_path} 삭제 실패. {e}")

    print("이전 데이터 파일 삭제 완료.")

    # Clear database
    try:
        from src.utils import db_manager

        db_manager.clear_db()
        print(" - 데이터베이스 초기화됨.")
    except Exception as e:
        print(f"오류: 데이터베이스 초기화 실패. {e}")

    return True


if __name__ == "__main__":
    # Example usage: run this script directly to clear data
    clear_generated_data_files()
