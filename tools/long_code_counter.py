import pandas as pd

# Load CSV
df = pd.read_csv("matched_all_yml_with_flags_filtered.csv")

# Define the filter on MotherLine
def range_exceeds_1000(mother_line):
    try:
        num1, num2 = eval(mother_line)
        return (num2 - num1) > 500
    except:
        return False

# Apply both filters
filtered_df = df[
    df["MotherLine"].apply(range_exceeds_1000) &
    df["ID"].apply(lambda x: x.split("-")[-1] == "1")
]

# Output
print(f"Total entries where (num2 - num1 > 1000) and ID ends with '-1': {len(filtered_df)}")
for id_val, file_val in zip(filtered_df["ID"], filtered_df["File"]):
    print(f"{id_val}: {file_val}")
