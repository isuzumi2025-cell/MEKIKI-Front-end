"""環境チェックスクリプト (ASCII版)"""
import sys
import os
from pathlib import Path

print("=" * 50)
print("MEKIKI Development Environment Check")
print("=" * 50)

# Python version
print(f"\n[Python] {sys.version}")

# Load .env
from dotenv import load_dotenv
load_dotenv(".env")

# Check API keys
gemini_key = os.getenv("GEMINI_API_KEY", "")
openai_key = os.getenv("OPENAI_API_KEY", "")

print(f"\n[API Keys]")
print(f"  GEMINI_API_KEY: {'OK' if gemini_key and 'ここに' not in gemini_key else 'NOT SET'}")
print(f"  OPENAI_API_KEY: {'OK' if openai_key and openai_key.startswith('sk-') else 'NOT SET'}")

# Check credentials.json
creds_paths = [
    Path("credentials.json"),
    Path("credentials/service_account.json"),
    Path("C:/Users/raiko/OneDrive/Desktop/26/sitemap_pro/credentials/service_account.json"),
]

print(f"\n[Cloud Vision Credentials]")
found = False
for p in creds_paths:
    if p.exists():
        print(f"  OK: {p}")
        found = True
        break
if not found:
    print("  MISSING - HybridOCR will fail!")

# Check dependencies
print(f"\n[Dependencies]")
deps = [("PIL", "pillow"), ("customtkinter", "customtkinter"), ("google.cloud.vision", "google-cloud-vision"), ("fitz", "pymupdf"), ("openai", "openai")]
missing = []
for mod, pkg in deps:
    try:
        __import__(mod.split(".")[0])
        print(f"  OK: {mod}")
    except ImportError:
        print(f"  MISSING: {mod}")
        missing.append(pkg)

if missing:
    print(f"\n[Install Command]")
    print(f"  pip install {' '.join(missing)}")

print("\n" + "=" * 50)
