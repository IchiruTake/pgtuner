import os
import glob
from src.static.vars import SUGGESTION_ENTRY_READER_DIR


def cleanup():
    # Check the directory, remove all files except the latest one
    for dir_path in (SUGGESTION_ENTRY_READER_DIR, "log"):
        print(f"Cleaning up {dir_path}")
        files = glob.glob(f"{dir_path}/*")
        if len(files) > 1:
            files.sort(key=os.path.getmtime)
            for file in files[:-1]:
                os.remove(file)
        elif len(files) == 1:
            print(f"Only one file in {dir_path}, force full cleanup")
            os.remove(files[0])

if __name__ == "__main__":
    cleanup()
