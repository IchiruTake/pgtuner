import os
import glob
from src.static.vars import BACKUP_ENTRY_READER_DIR, SUGGESTION_ENTRY_READER_DIR, BASE_ENTRY_READER_DIR


def cleanup():
    # Check the directory, remove all files except the latest one
    for dir_path in (BACKUP_ENTRY_READER_DIR, SUGGESTION_ENTRY_READER_DIR, "log"):
        print(f"Cleaning up {dir_path}")
        files = glob.glob(f"{dir_path}/*")
        if len(files) > 1:
            files.sort(key=os.path.getmtime)
            for file in files[:-1]:
                os.remove(file)

if __name__ == "__main__":
    cleanup()
