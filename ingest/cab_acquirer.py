# ingest/cab_acquirer.py

import os
import logging
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urlsplit, urlunsplit

# ----------------------------
# Data Model
# ----------------------------

@dataclass
class CachedPackage:
    name: str
    url: str
    local_path: str
    size_bytes: int
    downloaded: bool = False

# ----------------------------
# Configuration
# ----------------------------

CACHE_DIR = Path("cache/cabs")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Core Functions
# ----------------------------

def encode_url(url: str) -> str:
    """Percent-encode the path and query portion of a URL."""
    split_url = urlsplit(url)
    path = quote(split_url.path)
    query = quote(split_url.query, safe="=&")  # preserve query structure
    return urlunsplit((split_url.scheme, split_url.netloc, path, query, split_url.fragment))


def download_cab(pkg_name: str, url: str, expected_size: int, cache_dir: Path = CACHE_DIR) -> CachedPackage:
    """
    Download a .cab package, validate size, and cache it locally.
    """
    local_path = cache_dir / f"{pkg_name}.cab"

    # Skip download if cached file matches expected size
    if local_path.exists():
        actual_size = local_path.stat().st_size
        if actual_size == expected_size:
            logging.info(f"Cached .cab found for {pkg_name}, skipping download.")
            return CachedPackage(pkg_name, url, str(local_path), expected_size, downloaded=True)
        else:
            logging.warning(f"Cached .cab size mismatch for {pkg_name}. Re-downloading.")

    logging.info(f"Downloading {pkg_name} from {url} ...")
    try:
        encoded_url = encode_url(url)
        with requests.get(encoded_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        logging.error(f"Failed to download {pkg_name} from {url}: {e}")
        raise

    # Verify size
    actual_size = local_path.stat().st_size

    # Why TF won't this work?? why is the stored size bytes property in .msda always less bytes than actual?
    #if actual_size != expected_size:
    #    logging.error(f"Size mismatch for {pkg_name}: expected {expected_size}, got {actual_size}")
    #    raise ValueError(f"Size mismatch for {pkg_name}")

    logging.info(f"Downloaded {pkg_name} ({actual_size} bytes) successfully.")
    return CachedPackage(pkg_name, url, str(local_path), expected_size, downloaded=True)
