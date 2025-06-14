# From YAML to Java: Bridging API Taint Summaries and Real Usage for Code Analysis Systems

This project presents **YAML2Code**, a dataset construction and static analysis pipeline that aligns CodeQL-style YAML taint summaries with real-world Java code. The system extracts semantically meaningful method call instances from large Java codebases and matches them against declarative API specifications, enabling function-level reasoning grounded in both symbolic and contextual signals. The resulting dataset supports research in software security, static analysis, and the development of LLM-based code understanding systems.
## Overview

This project builds an instance-level dataset by:

- Parsing YAML-based summaries of Java APIs, particularly those specifying taint flows.
- Analyzing large-scale Java codebases to identify and extract matching method call sites.
- Recording contextual information including enclosing methods, declared types, argument mappings, and precise code locations.
- Structuring the outputs into a machine-readable format for downstream use in program analysis and learning-based models.

## Features

- Support for parsing taint-style CodeQL YAML summaries.
- Accurate function call matching based on name, argument type, and class imports.
- Import-based package filtering to improve precision and reduce search time.
- Extraction of surrounding method body ("MotherBody") and line span ("MotherLine").
- Configurable support for unmatched entry inspection and false negative analysis.
- Dataset output in CSV format with traceable and structured IDs.

## Dataset Structure

Each dataset row includes:

| Field          | Description |
|----------------|-------------|
| `ID`           | Unique identifier encoding YAML model, entry index, and match count |
| `Matched`      | Match status (`T` for true, `F` for false) |
| `Model`        | High-level model name (e.g., `java.lang`) |
| `Package`      | Declared package of the target class |
| `FunctionName` | Name of the function being matched |
| `Summary`      | Parsed YAML summary as a list |
| `File`         | Java source file containing the call |
| `LineNumber`   | Line number of the matched invocation |
| `LineContent`  | Code line of the matched invocation |
| `MotherLine`   | Tuple indicating the start and end line of the enclosing method |
| `MotherBody`   | Extracted source code of the enclosing method |
| `DeclaredType` | Variable type (if available) used in the invocation |

## Applications

- Training data for LLMs focused on security reasoning and static analysis.
- Benchmarking dataset for function-level taint tracking tools.
- Source-grounded prompt construction for code generation or summarization tasks.

## Acknowledgement

This project was conducted as part of the UCLA Software Engineering and Analysis Laboratory (SEAL). The author sincerely thanks Professor Miryung Kim, Dr. Burak Yetistiren, and Dr. Hong Jin Kang for their invaluable guidance and support throughout the project. Their mentorship provided critical insight into software analysis and dataset construction, and this work would not have been possible without their advice.

The author also appreciates the feedback and encouragement from SEAL lab members, which greatly contributed to shaping the direction and scope of this work.

## Citation

If you use this code or dataset in your research, please cite:

```
Pei-Ying Li. *From YAML to Java: Bridging API Taint Summaries and Real Usage for Code Analysis Systems*. UCLA Computer Science Capstone Project, 2025.
```
