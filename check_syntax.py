import sys
import ast

file_path = r"c:\Users\raiko\OneDrive\Desktop\26\OCR\app\gui\windows\advanced_comparison_view.py"

try:
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
    ast.parse(source)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Syntax Error: {e}")
    print(f"Line: {e.lineno}, Offset: {e.offset}")
    print(f"Text: {e.text}")
except Exception as e:
    print(f"Error: {e}")
