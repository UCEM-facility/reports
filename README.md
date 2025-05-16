# reports
Generation of RTF reports extracted from ThermoFisher XML files

This script parses XML files from ThermoFisher's EPU, extracts various parameters, and writes it to a rich-text format (RTF) file.

# Usage

`tfs_xml2rtf.py <options>`

By default, the script looks in the directory `Images-Disc1` for XML files, but this default can be overridden. See below for command-line options.

![Screenshot_2025-05-16_17-15-49](https://github.com/user-attachments/assets/12c0a044-22cb-4350-952d-13e509e2f73d)

# Parameters

These settings affect multiple steps.

| Flag            | Type  | Default       | Description |
| --------------- | ----- | ------------- | ------------ |
| `--directory`   | ANY   | Images-Disc1  | Top-level images directory |
| `--calibration` | ANY   | None          | Magification-calibration Excel file |
| `--output`      | ANY   | report.rtf    | Output RTF report |
| `--no_scan`     | BOOL  | False         | Flag to skip EER scan |
| `--progress`    | BOOL  | False         | Flag to show progress bar |
| `--verbosity`   | INT   | 1             | Verbosity level (0..4) |
| `--debug`       | BOOL  | False         | Debugging mode |
