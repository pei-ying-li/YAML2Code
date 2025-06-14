import ast
import re
import os
import pandas as pd
from tqdm import tqdm

# Load existing match results
df = pd.read_csv("matched_all_yml_with_flags_filtered.csv")

# Filter only unmatched rows
df_false = df[df["Matched"] == "F"].copy()

# Extract fields from summary
def extract_summary_fields(summary_str):
    try:
        parsed = ast.literal_eval(summary_str)
        if isinstance(parsed, list) and len(parsed) > 4:
            arg_signature = parsed[4]
            types_list = []
            if arg_signature and arg_signature != "()":
                types_list = [
                    t.strip().split()[-1].split(".")[-1] for t in arg_signature.strip("()").split(",")
                ]
            return parsed[0], parsed[1], parsed[3], len(types_list), types_list, parsed, str(parsed)
    except:
        return None, None, None, None, None, summary_str, summary_str

java_files = []
for root, _, files in os.walk("data/empty"):
    for file in files:
        if file.endswith(".java"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            java_files.append({
                "filename": os.path.relpath(path, "data"),
                "lines": code.splitlines(),
                "code": code
            })

method_pattern = re.compile(r"^\s*(public|private|protected)?\s+\w.*\)\s*\{")
pattern_template = re.compile(r"(\b\w+)\.{}\s*\(")

def types_match(expected, actual):
    if len(expected) != len(actual):
        return False
    return all(e == "Any" or a == "Any" or e.lower() == a.lower() for e, a in zip(expected, actual))

updated_rows = []

for idx, entry in tqdm(df_false.iterrows(), total=len(df_false)):
    model, package, function, argcount, paramtypes, parsed_summary, summary_str = extract_summary_fields(entry["Summary"])
    if not model:
        continue

    for java_file in java_files:
        java_lines = java_file["lines"]
        filename = java_file["filename"]

        import_lines = [line.strip() for line in java_lines if line.strip().startswith("import ")]
        imported_packages = [line[len("import "):].rstrip(";") for line in import_lines]
        expected_class = package.split(".")[-1]
        if not any(pkg.endswith(f".{expected_class}") or pkg == expected_class for pkg in imported_packages):
            continue

        method_boundaries = []
        brace_stack = []
        inside_method = False
        current_method = None

        for i, line in enumerate(java_lines):
            if not inside_method and method_pattern.match(line):
                current_method = {"start": i, "signature": line.strip()}
                inside_method = True
                brace_stack = ["{"] if "{" in line else []
            elif inside_method:
                brace_stack.extend([b for b in line if b == "{"])
                brace_stack = brace_stack[:len(brace_stack) - line.count("}")]
                if not brace_stack:
                    current_method["end"] = i
                    current_method["body"] = "\n".join(java_lines[current_method["start"]:i+1])
                    current_method["lines"] = java_lines[current_method["start"]:i+1]
                    method_boundaries.append(current_method)
                    inside_method = False

        pattern = pattern_template.pattern.format(re.escape(function))
        regex = re.compile(pattern)

        for line_idx, line in enumerate(java_lines, start=1):
            match = regex.search(line)
            if not match:
                continue
            caller_var = match.group(1)

            arg_list_match = re.search(rf"{re.escape(function)}\s*\((.*?)\)", line)
            if arg_list_match:
                args = [arg.strip() for arg in arg_list_match.group(1).split(",") if arg.strip()]
                actual_arg_count = len(args)
                actual_types = ["Any"] * actual_arg_count
            else:
                actual_arg_count = 0
                actual_types = []

            mother_body = ""
            start_line = end_line = None
            mother_lines = []

            for method in method_boundaries:
                if method["start"] <= line_idx - 1 <= method["end"]:
                    start_line = method["start"] + 1
                    end_line = method["end"] + 1
                    mother_body = method["body"]
                    mother_lines = method["lines"]
                    break

            declared_type = None
            declaration_pattern = re.compile(rf"\b(\w+)\s*<[^>]*>?\s+{re.escape(caller_var)}\b|\b(\w+)\s+{re.escape(caller_var)}\b")
            for body_line in mother_lines:
                decl_match = declaration_pattern.search(body_line)
                if decl_match:
                    declared_type = decl_match.group(1) or decl_match.group(2)
                    break

            expected_type = package.split(".")[-1]
            expected_params = paramtypes if isinstance(paramtypes, list) else []

            if declared_type == expected_type and actual_arg_count == argcount and types_match(expected_params, actual_types):
                df.loc[idx, "Matched"] = "T"
                df.loc[idx, "File"] = filename
                df.loc[idx, "LineNumber"] = line_idx
                df.loc[idx, "LineContent"] = line.strip()
                df.loc[idx, "MotherLine"] = (start_line, end_line)
                df.loc[idx, "MotherBody"] = mother_body
                df.loc[idx, "DeclaredType"] = declared_type
                break

# Save updated DataFrame
df.to_csv("matched_all_yml_with_flags_filtered.csv", index=False)
print("Updated file saved to matched_all_yml_with_flags_filtered.csv")
