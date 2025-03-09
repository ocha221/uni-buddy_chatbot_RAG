import json
import os
import re


def simplify_semester(directory):
    modified_count = 0

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "semester" in data and not isinstance(data["semester"], int):
                        semester_str = data["semester"]
                        match = re.search(r"(\d+)", semester_str)
                        if match:
                            data["semester"] = int(match.group(1))
                            with open(file_path, "w", encoding="utf-8") as f:
                                json.dump(data, f, indent=2, ensure_ascii=False)
                            print(
                                f"Updated {file_path}: changed semester from '{semester_str}' to {data['semester']}"
                            )
                            modified_count += 1
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

    print(f"\nTotal files modified: {modified_count}")


if __name__ == "__main__":
    import sys

    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    simplify_semester(directory)
