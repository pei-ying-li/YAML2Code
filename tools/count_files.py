import os

folder_path = "data"
java_file_count = 0

for root, dirs, files in os.walk(folder_path):
    java_file_count += sum(1 for file in files if file.endswith(".java"))

print(f"Total .java files: {java_file_count}")
