# ingest/cab_extractor.py

import os
import logging
import zipfile
import shutil
from pathlib import Path
from typing import List
import subprocess

# ----------------------------
# Configuration
# ----------------------------
EXTRACTED_DIR = Path("cache/extracted")
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Helpers
# ----------------------------

def extract_cab(cab_path: Path, dest_dir: Path = EXTRACTED_DIR) -> Path:
    """
    Extract a .cab file to dest_dir/package_name/
    """
    package_name = cab_path.stem
    package_dir = dest_dir / package_name
    package_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f"Extracting CAB {cab_path} → {package_dir}")

    try:
        # Prefer 7z if available
        subprocess.run(
            ["7z", "x", str(cab_path), f"-o{package_dir}"], check=True, capture_output=True
        )
    except FileNotFoundError:
        # fallback: Windows native expand
        if os.name == "nt":
            # ADD -F:* to extract all files
            subprocess.run(["expand", str(cab_path), "-F:*", str(package_dir)], check=True)
        else:
            raise RuntimeError("7z is required to extract CAB files on non-Windows systems")

    return package_dir

def extract_mshc(mshc_path: Path) -> Path:
    """
    Extract a .mshc ZIP file to a folder mshc_extracted/ next to the .mshc file
    """
    extract_dir = mshc_path.parent / f"{mshc_path.stem}_extracted"
    extract_dir.mkdir(exist_ok=True)

    logging.info(f"Extracting MSHC {mshc_path} → {extract_dir}")

    with zipfile.ZipFile(mshc_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    return extract_dir

def extract_all_cabs(cab_paths: List[Path]) -> List[Path]:
    """
    Extract all CABs and any MSHC files within them.
    Returns list of extracted package directories.
    """
    extracted_packages = []

    for cab_path in cab_paths:
        try:
            package_dir = extract_cab(cab_path)
            extracted_packages.append(package_dir)

            # Extract all MSHC files in the package dir
            for mshc_file in package_dir.glob("*.mshc"):
                extract_mshc(mshc_file)

        except Exception as e:
            logging.error(f"Failed to extract {cab_path}: {e}")

    return extracted_packages
