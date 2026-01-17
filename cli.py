# ./ cli.py

import argparse
import logging
from pathlib import Path
from ingest.msda import parse_msda, catalog_to_json
from ingest.cab_acquirer import download_cab, CACHE_DIR, CachedPackage
from ingest.cab_extractor import extract_all_cabs
from ingest.mshc_to_docfx import generate_toc

# ----------------------------
# CLI Helpers
# ----------------------------

def process_catalog(
    msda_file: str,
    output_json: str = None,
    download_cabs: bool = False,
    extract: bool = False,
    docfx: bool = False
):
    """
    Main function: parse MSDA and optionally download, extract, and generate DocFX content.
    """
    logging.info(f"Parsing MSDA catalog: {msda_file}")
    catalog = parse_msda(msda_file)

    if output_json:
        catalog_to_json(catalog, output_json)

    cached_packages = []

    if download_cabs:
        logging.info("Downloading referenced CAB packages...")
        for book in catalog.books:
            for pkg in book.packages:
                try:
                    cached_pkg = download_cab(pkg.name, pkg.url, pkg.size_bytes)
                    cached_packages.append(cached_pkg)
                except Exception as e:
                    logging.error(f"Failed to download package {pkg.name}: {e}")

    extracted_dirs = []
    if extract:
        if not cached_packages:
            # No packages downloaded in this run, check cache folder
            logging.info("No downloaded packages in memory; scanning cache for CABs...")
            cab_files = list(CACHE_DIR.glob("*.cab"))
            cached_packages = [CachedPackage(name=f.stem, url=None, size_bytes=None, local_path=f, downloaded=True)
                               for f in cab_files]
        if cached_packages:
            logging.info("Extracting CAB and MSHC packages...")
            cab_paths = [Path(pkg.local_path) for pkg in cached_packages if pkg.downloaded]
            extracted_dirs = extract_all_cabs(cab_paths)

    if docfx:
        if not extract:
            logging.warning("--docfx used without --extract; DocFX content will be generated from existing extracted folders")
        logging.info("Generating DocFX content...")
        generate_toc()

    logging.info("Processing complete.")
    return catalog, cached_packages, extracted_dirs

# ----------------------------
# CLI Entry Point
# ----------------------------

def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = argparse.ArgumentParser(
        description="MSDA Catalog Processor & CAB Downloader/Extractor/DocFX Generator"
    )
    parser.add_argument("msda_file", help="Path to the .msda catalog file")
    parser.add_argument("-o", "--output", help="Output JSON catalog path", default=None)
    parser.add_argument(
        "--download", help="Download all referenced CAB packages", action="store_true"
    )
    parser.add_argument(
        "--extract", help="Extract CAB and MSHC packages after download", action="store_true"
    )
    parser.add_argument(
        "--docfx", help="Generate DocFX-ready content from extracted MSHC folders", action="store_true"
    )

    args = parser.parse_args()

    # Warn if --extract is used without --download
    if args.extract and not args.download:
        logging.warning("--extract used without --download; extraction will only work on existing cached CABs.")

    catalog, cached_packages, extracted_dirs = process_catalog(
        msda_file=args.msda_file,
        output_json=args.output,
        download_cabs=args.download,
        extract=args.extract,
        docfx=args.docfx
    )

    # Log summary
    logging.info(f"Parsed {len(catalog.books)} books from MSDA catalog.")
    logging.info(f"Downloaded {len(cached_packages)} CAB packages.")
    logging.info(f"Extracted {len(extracted_dirs)} directories.")
    if args.docfx:
        logging.info("DocFX content generated in docfx_content/")

if __name__ == "__main__":
    main()