"""
One-time backfill script to populate the ingested_documents table in Supabase
with metadata for files that were already ingested into Pinecone.
"""
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from database import upsert_ingested_document

DATA_DIR = "./data"

# These are the files that were successfully ingested into Pinecone (8,785 chunks total).
# Chunk counts are approximated from the ingestion logs.
files_to_backfill = [
    {"filename": "DoppelgangerR1_R20.pdf", "file_type": "PDF"},
    {"filename": "DoppelgangerR21_R51.pdf", "file_type": "PDF"},
    {"filename": "File1_Sections1_9B.pdf", "file_type": "PDF"},
    {"filename": "File2_Sections10_10C.pdf", "file_type": "PDF"},
    {"filename": "GMT20260108-120125_Recording.cc.vtt", "file_type": "VTT"},
    {"filename": "Income-tax-Act-1961_2026_2026-06-18_02-47-37_b9326c_en.pdf", "file_type": "PDF"},
    {"filename": "IncometaxAmendmentRules2026.pdf", "file_type": "PDF"},
    {"filename": "THE INCOME-TAX ACT 2025 14-02-26.pdf", "file_type": "PDF"},
    {"filename": "business income v1.pptx", "file_type": "PPTX"},
    {"filename": "Income Tax Act - 2025 - Definitive Guide_6Nov2025_ print file.pdf", "file_type": "PDF"},
]

print("Backfilling ingested_documents table in Supabase...")

for file_info in files_to_backfill:
    filename = file_info["filename"]
    file_type = file_info["file_type"]
    file_path = os.path.join(DATA_DIR, filename)
    
    if os.path.exists(file_path):
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
    else:
        size_mb = 0.0
        print(f"  [NOTE] File not found locally: {filename} (will use 0 MB)")
    
    # We don't have exact chunk counts from the previous run, so use 0 as placeholder.
    # These will be updated accurately when re-ingestion happens.
    upsert_ingested_document(filename, file_type, size_mb, chunk_count=0)

print("\n[SUCCESS] Backfill complete! All previously ingested files are now tracked in Supabase.")
