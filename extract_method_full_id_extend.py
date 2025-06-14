import ast
import re
import os
import pandas as pd
from tqdm import tqdm

# Load existing matched entries
matched_df = pd.read_csv("matched_all_yml_with_flags.csv")
matched_df["LineNumber"] = matched_df["LineNumber"].fillna("").astype(str)

# Load YAML summary
df = pd.read_csv("data/yaml_summaries.csv")

# Parse YAML summary fields
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
            "Model": None, "Package": None, "FunctionName": None,
            "ArgCount": None, "ParamTypes": None,
            "Summary": summary_str, "SummaryStr": summary_str
        })

df = pd.concat([df, df["Summary"].apply(extract_summary_fields)], axis=1)

# Load all .java files under flink-streaming-java
java_files = []
for root, _, files in os.walk("data/dubbo-metadata"):
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

# Match helper
def types_match(expected, actual):
    if len(expected) != len(actual): return False
    return all(e == "Any" or a == "Any" or e.lower() == a.lower() for e, a in zip(expected, actual))

method_pattern = re.compile(r"^\s*(public|private|protected)?\s+\w.*\)\s*\{")
pattern_template = re.compile(r"(\b\w+)\.{}\s*\(")

# Build model for inserting
insertion_rows = []
modification_map = {}

for _, entry in tqdm(df.iterrows(), total=len(df)):
    matched = False
    for java_file in java_files:
        java_lines = java_file["lines"]
        filename = java_file["filename"]

        # Extract method boundaries
        methods = []
        brace_stack = []
        inside = False
        current = None
        for i, line in enumerate(java_lines):
            if not inside and method_pattern.match(line):
                current = {"start": i, "signature": line.strip()}
                inside = True
                brace_stack = ["{"] if "{" in line else []
            elif inside:
                brace_stack += [b for b in line if b == "{"]
                brace_stack = brace_stack[:len(brace_stack) - line.count("}")]
                if not brace_stack:
                    current["end"] = i
                    current["body"] = "\n".join(java_lines[current["start"]:i+1])
                    current["lines"] = java_lines[current["start"]:i+1]
                    methods.append(current)
                    inside = False

        # Pattern to find function call
        pattern = pattern_template.pattern.format(re.escape(entry.FunctionName))
        regex = re.compile(pattern)

        for line_idx, line in enumerate(java_lines, start=1):
            m = regex.search(line)
            if not m:
                continue

            caller_var = m.group(1)
            args = []
            arg_match = re.search(rf"{re.escape(entry.FunctionName)}\s*\((.*?)\)", line)
            if arg_match:
                args = [x.strip() for x in arg_match.group(1).split(",") if x.strip()]
            actual_types = ["Any"] * len(args)

            # Find method this line belongs to
            method_info = next((m for m in methods if m["start"] <= line_idx-1 <= m["end"]), None)
            start_line = method_info["start"] + 1 if method_info else ""
            end_line = method_info["end"] + 1 if method_info else ""
            body = method_info["body"] if method_info else ""
            method_lines = method_info["lines"] if method_info else []

            # Find declared type of caller_var
            declared_type = ""
            type_pattern = re.compile(rf"\b(\w+)\s*<[^>]*>?\s+{caller_var}\b|\b(\w+)\s+{caller_var}\b")
            for l in method_lines:
                m2 = type_pattern.search(l)
                if m2:
                    declared_type = m2.group(1) or m2.group(2)
                    break

            expected_type = entry.Package.split(".")[-1]
            expected_params = entry.ParamTypes if isinstance(entry.ParamTypes, list) else []

            if declared_type == expected_type and len(args) == entry.ArgCount and types_match(expected_params, actual_types):
                # Case 1: Upgrade existing F row
                cond = (
                    (matched_df["Model"] == entry.Model) &
                    (matched_df["Package"] == entry.Package) &
                    (matched_df["FunctionName"] == entry.FunctionName) &
                    (matched_df["Matched"] == "F")
                )
                match_row = matched_df[cond]
                if not match_row.empty:
                    idx = match_row.index[0]
                    matched_df.loc[idx, "Matched"] = "T"
                    matched_df.loc[idx, "File"] = filename
                    matched_df.loc[idx, "LineNumber"] = line_idx
                    matched_df.loc[idx, "LineContent"] = line.strip()
                    matched_df.loc[idx, "MotherLine"] = (start_line, end_line)
                    matched_df.loc[idx, "MotherBody"] = body
                    matched_df.loc[idx, "DeclaredType"] = declared_type
                    matched = True
                    break
                else:
                    # Case 2: Prepare for insertion
                    key = f"{entry.Model}-{entry.Package}-{entry.FunctionName}"
                    insertion_rows.append((key, {
                        "ID": "",  # ID will be filled during insertion
                        "Matched": "T",
                        "Model": entry.Model,
                        "Package": entry.Package,
                        "FunctionName": entry.FunctionName,
                        "Summary": entry.SummaryStr,
                        "File": filename,
                        "LineNumber": line_idx,
                        "LineContent": line.strip(),
                        "MotherLine": (start_line, end_line),
                        "MotherBody": body,
                        "DeclaredType": declared_type
                    }))
                    matched = True
                    break
        if matched:
            break

# Insert new matches after matching IDs
final_rows = []
for i, row in matched_df.iterrows():
    final_rows.append(row)
    key = f"{row['Model']}-{row['Package']}-{row['FunctionName']}"
    inserted = [r for k, r in insertion_rows if k == key]
    for r in inserted:
        base_id = row["ID"]
        prefix = "-".join(base_id.split("-")[:-1])
        new_index = int(base_id.split("-")[-1]) + 1
        r["ID"] = f"{prefix}-{new_index}"
        final_rows.append(pd.Series(r))

# Save final result
final_df = pd.DataFrame(final_rows)
final_df.to_csv("matched_all_yml_with_flags.csv", index=False)
print("Updated and saved to matched_all_yml_with_flags.csv")
