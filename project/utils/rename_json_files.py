import os
import sys
from pathlib import Path


def rename_json_files(directory: str) -> None:
    dir_path = Path(directory)

    for path in dir_path.rglob("*.json"):
        if path.is_file():
            parent_dir = path.parent
            old_name = path.stem
            new_name = f"{old_name}.course.json"
            new_path = parent_dir / new_name
            try:
                path.rename(new_path)
                print(f"Renamed: {path} -> {new_path}")
            except Exception as e:
                print(f"Error renaming {path}: {str(e)}")


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "."

    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' does not exist")
        sys.exit(1)

    print(f"Starting to rename JSON files in: {directory}")
    rename_json_files(directory)
    print("Finished renaming files")
