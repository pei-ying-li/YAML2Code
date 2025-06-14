import pandas as pd

# Load CSV
df = pd.read_csv("matched_all_yml_with_flags_full.csv")

# Define the filter condition
def is_excluded_row(row):
    try:
        num1, num2 = eval(row["MotherLine"])
        return (num2 - num1) > 1000 and row["ID"].split("-")[-1] == "1"
    except:
        return False

# Apply filter and remove matching rows
filtered_df = df[~df.apply(is_excluded_row, axis=1)]

# Save to a new CSV
filtered_df.to_csv("matched_all_yml_with_flags_filtered.csv", index=False)

print(f"Filtered file saved with {len(filtered_df)} rows.")
