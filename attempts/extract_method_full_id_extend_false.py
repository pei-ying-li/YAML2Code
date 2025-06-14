import ast
import re
import os
import pandas as pd
from tqdm import tqdm

# Load existing matched entries
matched_df = pd.read_csv("matched_all_yml_with_flags.csv")
matched_df["LineNumber"] = matched_df["LineNumber"].fillna("").astype(str)

# Filter only unmatched entries (Matched == "F")
unmatched_df = matched_df[matched_df["Matched"] == "F"]

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
for root, _, files in os.walk("bp_codeql/data/impala-fe/org/apache/impala/analysis"):
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
    if len(expected) != len(actual):
        return False
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

        # Extract all method boundaries (keep all, not filtered yet)
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
                    current["body"] = "\n".join(java_lines[current["start"]:i + 1])
                    current["lines"] = java_lines[current["start"]:i + 1]
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

            # Find method this line belongs to (any method, for declared_type detection)
            method_info = next(
                (m for m in methods if m["start"] <= line_idx - 1 <= m["end"]),
                None
            )

            start_line = method_info["start"] + 1 if method_info else ""
            end_line = method_info["end"] + 1 if method_info else ""
            body = method_info["body"] if method_info else line.strip()
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
                # Only modify rows in unmatched_df (Matched == "F")
                cond = (
                    (unmatched_df["Model"] == entry.Model) &
                    (unmatched_df["Package"] == entry.Package) &
                    (unmatched_df["FunctionName"] == entry.FunctionName)
                )
                match_row = unmatched_df[cond]
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
        if matched:
            break

# Postprocess: refine MotherBody to only the closest public/private/protected method
for idx, row in matched_df.iterrows():
    if row["Matched"] != "T" or pd.isna(row["LineNumber"]):
        continue

    filename = row["File"]
    try:
        line_idx = int(row["LineNumber"])
    except:
        continue

    java_file = next((f for f in java_files if f["filename"] == filename), None)
    if java_file is None:
        continue

    java_lines = java_file["lines"]

    # Re-extract methods
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
                current["body"] = "\n".join(java_lines[current["start"]:i + 1])
                current["lines"] = java_lines[current["start"]:i + 1]
                methods.append(current)
                inside = False

    # Find the closest public/private/protected method block
    method_info = next(
        (m for m in methods 
         if method_pattern.match(m["signature"]) and m["start"] <= line_idx - 1 <= m["end"]),
        None
    )

    if method_info:
        matched_df.loc[idx, "MotherBody"] = method_info["body"]
        matched_df.loc[idx, "MotherLine"] = (method_info["start"] + 1, method_info["end"] + 1)

# Save final result
matched_df.to_csv("matched_all_yml_with_flags.csv", index=False)
print("Updated and saved to matched_all_yml_with_flags.csv")
