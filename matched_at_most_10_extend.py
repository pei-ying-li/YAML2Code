import ast
import re
import os
import pandas as pd
from tqdm import tqdm

# Load YAML CSV
df = pd.read_csv("data/yaml_summaries.csv")

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
            return pd.Series({
                "Model": parsed[0],
                "Package": parsed[1],
                "FunctionName": parsed[3],
                "ArgCount": len(types_list),
                "ParamTypes": types_list,
                "Summary": parsed,
                "SummaryStr": str(parsed)
            })
    except Exception:
        return pd.Series({
            "Model": None,
            "Package": None,
            "FunctionName": None,
            "ArgCount": None,
            "ParamTypes": None,
            "Summary": summary_str,
            "SummaryStr": summary_str
        })

summary_fields = df["Summary"].apply(extract_summary_fields)
df = pd.concat([df, summary_fields], axis=1)

# Prepare Java files
java_files = []
for root, _, files in os.walk("data"):
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

model_id_map = {}
model_counter = 1
match_counter = {}
all_matches = []

for entry_id, (_, entry) in enumerate(tqdm(df.iterrows(), total=len(df)), start=1):
    model = entry.Model
    if model not in model_id_map:
        model_id_map[model] = model_counter
        model_counter += 1
    model_id = model_id_map[model]

    match_counter_key = f"{entry.Model}-{entry.Package}-{entry.FunctionName}-{str(entry.ParamTypes)}-{entry_id}"
    match_counter[match_counter_key] = 0

    matched = False

    for java_file in java_files:
        java_lines = java_file["lines"]
        filename = java_file["filename"]

        import_lines = [line.strip() for line in java_lines if line.strip().startswith("import ")]
        imported_packages = [line[len("import "):].rstrip(";") for line in import_lines]

        expected_class = entry.Package.split(".")[-1]
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

        pattern = pattern_template.pattern.format(re.escape(entry.FunctionName))
        regex = re.compile(pattern)

        for line_idx, line in enumerate(java_lines, start=1):
            match = regex.search(line)
            if not match:
                continue
            caller_var = match.group(1)

            arg_list_match = re.search(rf"{re.escape(entry.FunctionName)}\s*\((.*?)\)", line)
            if arg_list_match:
                args = [arg.strip() for arg in arg_list_match.group(1).split(",") if arg.strip()]
                actual_arg_count = len(args)
                actual_types = ["Any"] * actual_arg_count
            else:
                actual_arg_count = 0
                actual_types = []

            mother_function = ""
            start_line = end_line = None
            mother_body = ""
            mother_lines = []
            for method in method_boundaries:
                if method["start"] <= line_idx - 1 <= method["end"]:
                    mother_function = method["signature"]
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

            expected_type = entry.Package.split(".")[-1]
            expected_params = entry.ParamTypes if isinstance(entry.ParamTypes, list) else []

            if declared_type == expected_type and actual_arg_count == entry.ArgCount and types_match(expected_params, actual_types):
                match_counter[match_counter_key] += 1
                match_id = match_counter[match_counter_key]
                if match_id > 10:
                    continue
                unique_id = f"{entry.Model.replace('.', '-')}-model-{entry.Package.replace('.', '-')}-{entry.FunctionName}-{model_id}-{entry_id}-{match_id}"
                all_matches.append({
                    "ID": unique_id,
                    "Matched": "T",
                    "Model": entry.Model,
                    "Package": entry.Package,
                    "FunctionName": entry.FunctionName,
                    "Summary": entry.SummaryStr,
                    "File": filename,
                    "LineNumber": line_idx,
                    "LineContent": line.strip(),
                    "MotherLine": (start_line, end_line),
                    "MotherBody": mother_body,
                    "DeclaredType": declared_type
                })
                matched = True

    if not matched:
        match_counter[match_counter_key] += 1
        match_id = match_counter[match_counter_key]
        if match_id > 10:
            continue
        unique_id = f"{entry.Model.replace('.', '-')}-model-{entry.Package.replace('.', '-')}-{entry.FunctionName}-{model_id}-{entry_id}-{match_id}"
        all_matches.append({
            "ID": unique_id,
            "Matched": "F",
            "Model": entry.Model,
            "Package": entry.Package,
            "FunctionName": entry.FunctionName,
            "Summary": entry.SummaryStr,
            "File": "",
            "LineNumber": "",
            "LineContent": "",
            "MotherLine": "",
            "MotherBody": "",
            "DeclaredType": ""
        })

# Save output
final_df = pd.DataFrame(all_matches)
final_df.to_csv("result_remove_long.csv", index=False)
print("Full YAML entries with updated unique IDs saved to result_remove_long.csv")
