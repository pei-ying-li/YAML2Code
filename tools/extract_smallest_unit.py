import pandas as pd
import re

def extract_outer_enclosing_method(mother_body, mother_line_range, target_line_number):
    method_start_pattern = re.compile(r'^\s*(public|private|protected).*?\(.*?\)\s*(\{|$)')
    lines = mother_body.splitlines()
    start_line_in_file, _ = eval(mother_line_range)
    target_line = int(target_line_number)

    i = 0
    while i < len(lines):
        line = lines[i]

        match = method_start_pattern.match(line)
        if match:
            method_sig_lines = [line.strip()]
            method_start = i
            brace_count = line.count('{') - line.count('}')
            i += 1

            # If opening brace not in same line, scan further for it
            while brace_count == 0 and i < len(lines):
                brace_count += lines[i].count('{') - lines[i].count('}')
                method_sig_lines.append(lines[i].strip())
                i += 1

            method_end = i
            while brace_count > 0 and i < len(lines):
                brace_count += lines[i].count('{') - lines[i].count('}')
                i += 1
                method_end = i

            abs_start = method_start + start_line_in_file
            abs_end = method_end - 1 + start_line_in_file

            if abs_start <= target_line <= abs_end:
                return {
                    'Signature': method_sig_lines[0],
                    'Range': (abs_start, abs_end)
                }

        else:
            i += 1
    return None

if __name__ == "__main__":
    df = pd.read_csv("matched_all_yml_with_flags_full.csv")
    target_id = "java-lang-model-String-toLowerCase-6-95-141"
    row = df[df["ID"] == target_id]

    if not row.empty:
        line_number = row["LineNumber"].values[0]
        mother_line = row["MotherLine"].values[0]
        mother_body = row["MotherBody"].values[0]

        result = extract_outer_enclosing_method(mother_body, mother_line, line_number)

        if result:
            print("Enclosing Method Signature:", result["Signature"])
            print("Method Range in file:", result["Range"])
        else:
            print("No enclosing method found.")
    else:
        print(f"ID {target_id} not found in dataset.")
