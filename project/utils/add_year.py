import os
import json
import re
import sys
from collections import OrderedDict


def determine_year(semester_str):
    match = re.search(r"(\d+)", semester_str)
    if match:
        sem = int(match.group(1))
        if sem in [1, 2]:
            return 1
        elif sem in [3, 4]:
            return 2
        elif sem in [5, 6]:
            return 3
        elif sem in [7, 8]:
            return 4
    return None


def process_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f, object_pairs_hook=OrderedDict)
    except Exception as e:
        print(f"Failed to load {file_path}: {e}")
        return

    semester = content.get("semester", "")
    year = determine_year(semester)
    if year is None:
        print(
            f"Skipping {file_path} because of undetermined year from 'semester': {semester}"
        )
        return

    new_content = OrderedDict()
    inserted = False
    for key, value in content.items():
        new_content[key] = value
        if key == "course_code" and not inserted:
            new_content["year"] = year
            inserted = True

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(new_content, f, ensure_ascii=False, indent=2)
        print(f'Updated {file_path} with "year": {year}')
    except Exception as e:
        print(f"Failed to update {file_path}: {e}")


def process_directory(root_dir):
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                process_file(file_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 update_year_recursive.py <path_to_class_data_directory>")
    else:
        process_directory(sys.argv[1])
