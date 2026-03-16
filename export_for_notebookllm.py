import os
import subprocess
from pathlib import Path

def export_for_notebookllm():
    # Define paths
    base_dir = Path("~").expanduser() / "synsets"
    code_output = Path("~").expanduser() / "synset_code.txt"
    data_output = Path("~").expanduser() / "synset_data.txt"

    if not base_dir.exists():
        print(f"Error: {base_dir} does not exist.")
        return

    # Use git to list files
    try:
        os.chdir(base_dir)
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--cached"],
            capture_output=True,
            text=True,
            check=True
        )
        files = [Path(f) for f in result.stdout.splitlines()]
    except subprocess.CalledProcessError:
        print("Error: Could not list git files.")
        return

    code_files = []
    data_files = []

    for f in files:
        if f.suffix == ".log" or "debug" in str(f).lower():
            continue
            
        if f.is_file():
            if "license" in str(f).lower() or f.name.startswith("LICENSE"):
                code_files.append(f)
            elif len(f.parts) > 1 and f.parts[0] == "data":
                data_files.append(f)
            else:
                code_files.append(f)

    # Sorting
    def sort_code(p):
        name = str(p).lower()
        if "readme" in name: return (0, name)
        if "license" in name: return (2, name)
        return (1, name)
    
    # Strictly group data by directory, meta.json first in each dir
    def sort_data(p):
        # p.parent is the dir, p.name is the file
        folder = str(p.parent)
        is_meta = 0 if p.name == "meta.json" else 1
        return (folder, is_meta, p.name)
    
    code_files.sort(key=sort_code)
    data_files.sort(key=sort_data)

    with open(code_output, "w") as f_code, open(data_output, "w") as f_data:
        f_code.write("--- BEGIN CODE/DOCUMENTATION SUMMARY ---\n\n")
        for f in code_files:
            f_code.write(f"\n--- FILE: {f} ---\n\n")
            try:
                with open(f, "r", encoding="utf-8") as content:
                    f_code.write(content.read())
            except Exception as e:
                f_code.write(f"Error reading: {e}\n")
        f_code.write("\n--- END CODE SUMMARY ---\n")

        # Group data by directory for readability
        last_dir = None
        for f in data_files:
            if f.parent != last_dir:
                f_data.write(f"\n\n=== DIRECTORY: {f.parent} ===\n\n")
                last_dir = f.parent
            
            f_data.write(f"\n--- FILE: {f} ---\n\n")
            try:
                with open(f, "r", encoding="utf-8") as content:
                    f_data.write(content.read())
            except Exception as e:
                f_data.write(f"Error reading: {e}\n")

    print(f"Export complete.")
    print(f"Code summary: {code_output}")
    print(f"Data summary: {data_output}")

if __name__ == "__main__":
    export_for_notebookllm()
