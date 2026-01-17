# ingest/mshc_to_docfx.py

import os
import shutil
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List
from ingest.xhtml_to_docfx_md import convert_xhtml_to_markdown
from ingest.xhtml_to_docfx_md import extract_topic_metadata

# ----------------------------
# Configuration
# ----------------------------
EXTRACTED_DIR = Path("cache/extracted")
DOCFX_OUTPUT_DIR = Path("docfx_content")
ARTICLES_DIR = DOCFX_OUTPUT_DIR / "articles"
IMAGES_DIR = DOCFX_OUTPUT_DIR / "images"

ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

SEEN_UIDS = set()

# ----------------------------
# Helpers
# ----------------------------

def parse_metadata(metadata_path: Path) -> dict:
    """
    Parse metadata.xml from MSHC and return a mapping {html_file: title}.
    """
    if not metadata_path.exists():
        return {}

    tree = ET.parse(metadata_path)
    root = tree.getroot()
    mapping = {}

    # metadata.xml format: <Topic> elements with filename and title
    for topic in root.findall(".//Topic"):
        file_elem = topic.find("File")
        title_elem = topic.find("Title")
        if file_elem is not None and title_elem is not None:
            mapping[file_elem.text] = title_elem.text

    return mapping

def process_mshc_folder(mshc_folder: Path) -> List[dict]:
    toc_entries = []

    metadata_path = mshc_folder / "metadata.xml"
    html_map = parse_metadata(metadata_path)

    for html_file in mshc_folder.glob("*.html"):
        topic = extract_topic_metadata(html_file)

        # Skip duplicates
        if topic.uid in SEEN_UIDS:
            continue
        SEEN_UIDS.add(topic.uid)

        docfx_name = html_file.stem + ".md"
        dest_file = ARTICLES_DIR / docfx_name

        markdown = convert_xhtml_to_markdown(html_file, topic)
        dest_file.write_text(markdown, encoding="utf-8")

        toc_entries.append({
            "name": topic.title,
            "href": str(dest_file.relative_to(DOCFX_OUTPUT_DIR)).replace("\\", "/")
        })

    return toc_entries

def generate_toc(extracted_root: Path = EXTRACTED_DIR):
    """
    Walk all extracted CABs/MSHC folders and generate DocFX TOC.
    """
    all_toc = []

    for cab_dir in extracted_root.iterdir():
        if not cab_dir.is_dir():
            continue
        # Each CAB may have multiple *_extracted MSHC folders
        for mshc_dir in cab_dir.glob("*_extracted"):
            logging.info(f"Processing MSHC folder: {mshc_dir}")
            toc_entries = process_mshc_folder(mshc_dir)
            if toc_entries:
                all_toc.extend(toc_entries)

    # Write TOC YAML
    toc_yaml_path = DOCFX_OUTPUT_DIR / "toc.yml"
    with toc_yaml_path.open("w", encoding="utf-8") as f:
        for entry in all_toc:
            f.write(f"- name: \"{entry['name']}\"\n")
            f.write(f"  href: \"{entry['href']}\"\n")

    logging.info(f"TOC generated: {toc_yaml_path}")
    logging.info(f"Articles copied: {len(all_toc)}")
