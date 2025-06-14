import pandas as pd
from collections import defaultdict

# Load the CSV
df = pd.read_csv("matched_all_yml_with_flags_full.csv")

# Extract second-to-last and last parts
group_map = defaultdict(set)

for id_str in df["ID"].dropna():
    parts = id_str.strip().split("-")
    if len(parts) >= 2 and parts[-1].isdigit() and parts[-2].isdigit():
        second_last = parts[-2]
        last = parts[-1]
        group_map[second_last].add(last)

# Count how many unique last numbers per second-last
result = [(key, len(val)) for key, val in group_map.items()]
result.sort(key=lambda x: x[1], reverse=True)

# Print top 10
for sec_last, count in result[:10]:
    print(f"Second-last number: {sec_last}, Unique last-number count: {count}")
