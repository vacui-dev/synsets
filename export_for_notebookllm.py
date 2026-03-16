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

    # Use git to list files that are tracked or untracked but not ignored
    try:
        os.chdir(base_dir)
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--cached"],
            capture_output=True,
            text=True,
            check=True
        )
        files = result.stdout.splitlines()
    except subprocess.CalledProcessError:
        print("Error: Could not list git files.")
        return

    # Define common extensions for code vs data
    code_exts = {".py", ".md", ".json", ".yaml", ".sh", ".bash", ".gitignore"}
    
    with open(code_output, "w") as f_code, open(data_output, "w") as f_data:
        for file_path in files:
            full_path = base_dir / file_path
            if full_path.is_file():
                # Choose target based on extension
                target = f_code if full_path.suffix in code_exts else f_data
                
                target.write(f"\n--- FILE: {file_path} ---\n\n")
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        target.write(f.read())
                    target.write("\n")
                except Exception as e:
                    target.write(f"Error reading file: {e}\n")

    print(f"Export complete.")
    print(f"Code summary: {code_output}")
    print(f"Data summary: {data_output}")

if __name__ == "__main__":
    export_for_notebookllm()
