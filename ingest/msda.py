# ingest/msda.py

import logging
from dataclasses import dataclass, asdict
from typing import List, Optional
from lxml import html
import json

# ----------------------------
# Data Models
# ----------------------------

@dataclass
class PathInfo:
    languages: str
    membership: str
    name: str
    priority: int
    sku_id: int
    sku_name: str

@dataclass
class Package:
    name: str
    package_type: str
    format: str
    deployed: bool
    last_modified: str
    package_etag: str
    url: str
    size_bytes: int
    size_bytes_uncompressed: int

@dataclass
class Book:
    id: str
    locale: str
    name: str
    vendor: str
    description: Optional[str]
    paths: List[PathInfo]
    packages: List[Package]

@dataclass
class Catalog:
    catalog_locale: str
    books: List[Book]


# ----------------------------
# Helper Functions
# ----------------------------

def parse_paths(book_el) -> List[PathInfo]:
    paths = []
    for path_el in book_el.xpath('.//div[@class="paths"]/div[@class="path"]'):
        try:
            paths.append(PathInfo(
                languages=path_el.xpath('./span[@class="languages"]/text()')[0].strip(),
                membership=path_el.xpath('./span[@class="membership"]/text()')[0].strip(),
                name=path_el.xpath('./span[@class="name"]/text()')[0].strip(),
                priority=int(path_el.xpath('./span[@class="priority"]/text()')[0]),
                sku_id=int(path_el.xpath('./span[@class="skuId"]/text()')[0]),
                sku_name=path_el.xpath('./span[@class="skuName"]/text()')[0].strip(),
            ))
        except IndexError as e:
            logging.warning(f"Missing path element: {e}")
        except ValueError as e:
            logging.warning(f"Invalid number in path: {e}")
    return paths

def parse_packages(book_el) -> List[Package]:
    packages = []
    for pkg_el in book_el.xpath('.//div[@class="packages"]/div[@class="package"]'):
        try:
            packages.append(Package(
                name=pkg_el.xpath('./span[@class="name"]/text()')[0].strip(),
                package_type=pkg_el.xpath('./span[@class="packageType"]/text()')[0].strip(),
                format=pkg_el.xpath('./span[@class="packageFormat"]/text()')[0].strip(),
                deployed=pkg_el.xpath('./span[@class="deployed"]/text()')[0].strip().lower() == 'true',
                last_modified=pkg_el.xpath('./span[@class="last-modified"]/text()')[0].strip(),
                package_etag=pkg_el.xpath('./span[@class="package-etag"]/text()')[0].strip(),
                url=pkg_el.xpath('./a[@class="current-link"]/@href')[0].strip(),
                size_bytes=int(pkg_el.xpath('./span[@class="package-size-bytes"]/text()')[0]),
                size_bytes_uncompressed=int(pkg_el.xpath('./span[@class="package-size-bytes-uncompressed"]/text()')[0])
            ))
        except IndexError as e:
            logging.warning(f"Missing package element: {e}")
        except ValueError as e:
            logging.warning(f"Invalid number in package: {e}")
    return packages

def parse_books(tree) -> List[Book]:
    books = []
    # MSDA structure: <div class="book-group"> then <div class="book">
    book_elements = tree.xpath('//div[@class="book"]')
    for book_el in book_elements:
        try:
            book_id = book_el.xpath('.//span[@class="id"]/text()')[0].strip()
            name = book_el.xpath('.//span[@class="name"]/text()')[0].strip()
            locale = book_el.xpath('.//span[@class="locale"]/text()')[0].strip()
            vendor_el = book_el.xpath('.//span[@class="Vendor"]/text()')
            vendor = vendor_el[0].strip() if vendor_el else "Unknown"
            description_el = book_el.xpath('.//span[@class="Description"]/text()')
            description = description_el[0].strip() if description_el else None

            paths = parse_paths(book_el)
            packages = parse_packages(book_el)

            books.append(Book(
                id=book_id,
                name=name,
                locale=locale,
                vendor=vendor,
                description=description,
                paths=paths,
                packages=packages
            ))
        except IndexError as e:
            logging.warning(f"Failed parsing book element: {e}")
    return books

# ----------------------------
# Main Parsing Function
# ----------------------------

def parse_msda(file_path: str) -> Catalog:
    """
    Parse an MSDA catalog file and return a Catalog object.
    """
    try:
        tree = html.parse(file_path)
    except Exception as e:
        logging.error(f"Failed to parse MSDA file {file_path}: {e}")
        raise

    catalog_locale_elem = tree.xpath('//a[@class="catalog-locale-link"]')
    catalog_locale = catalog_locale_elem[0].text.strip() if catalog_locale_elem else "unknown"

    books = parse_books(tree)

    return Catalog(
        catalog_locale=catalog_locale,
        books=books
    )

# ----------------------------
# Optional: JSON export helper
# ----------------------------

def catalog_to_json(catalog: Catalog, json_path: str):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(asdict(catalog), f, indent=2)
    logging.info(f"Catalog JSON written to {json_path}")

# ----------------------------
# CLI support (optional)
# ----------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = argparse.ArgumentParser(description="Parse an MSDA catalog file into JSON")
    parser.add_argument("msda_file", help="Path to the .msda file")
    parser.add_argument("-o", "--output", help="Output JSON file path", default="catalog.json")
    args = parser.parse_args()

    catalog = parse_msda(args.msda_file)
    catalog_to_json(catalog, args.output)
