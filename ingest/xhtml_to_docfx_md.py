from pathlib import Path
from typing import Callable, List
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md
import re
import urllib.parse as urllib
from models.topic import TopicMetadata

# ------------------------------------------------------------
# Types
# ------------------------------------------------------------

DomTransform = Callable[[BeautifulSoup, TopicMetadata], None]

# ------------------------------------------------------------
# Core Helpers
# ------------------------------------------------------------

def extract_main_body(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Prefer MS Help mainBody; fall back to <body>.
    """
    main = soup.find(id="mainBody")
    return main if main else soup.body


def normalize_headings(soup: BeautifulSoup, topic: TopicMetadata):
    """
    DocFX expects a single H1 from the title/front matter.
    Demote all H1s to H2s.
    """
    for h1 in soup.find_all("h1"):
        h1.name = "h2"


def remove_non_content_elements(soup: BeautifulSoup, topic: TopicMetadata):
    """
    Remove elements that should never appear in markdown output.
    """
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()


# ------------------------------------------------------------
# Image Handling
# ------------------------------------------------------------

def rewrite_image_srcs_dom(soup: BeautifulSoup, topic: TopicMetadata):
    """
    Rewrite image sources to DocFX images directory.
    Skips data URIs and absolute URLs.
    """
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue

        if src.startswith("data:"):
            continue

        parsed = urllib.urlparse(src)
        if parsed.scheme in ("http", "https"):
            continue

        # Namespace images by topic UID to avoid collisions
        name = Path(parsed.path).name
        img["src"] = f"../images/{topic.uid}_{name}"


# ------------------------------------------------------------
# Link Handling
# ------------------------------------------------------------

def rewrite_mshelp_links_dom(soup: BeautifulSoup, topic: TopicMetadata):
    """
    Convert ms-xhelp links to DocFX <xref:UID> links.
    """
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("ms-xhelp:///"):
            continue

        parsed = urllib.urlparse(href)
        qs = urllib.parse_qs(parsed.query)
        help_id = qs.get("Id", [None])[0]

        if help_id:
            uid = help_id.replace("/", ".")
            a["href"] = f"<xref:{uid}>"


# ------------------------------------------------------------
# Alert Conversion
# ------------------------------------------------------------

def convert_alert_blocks_dom(soup: BeautifulSoup, topic: TopicMetadata):
    """
    Convert MTPS alert divs into semantic blockquotes.
    Actual DocFX syntax is emitted post-markdown.
    """
    alert_map = {
        "note": "NOTE",
        "tip": "TIP",
        "important": "IMPORTANT",
        "warning": "WARNING",
        "caution": "CAUTION",
    }

    for div in soup.find_all("div"):
        classes = [c.lower() for c in div.get("class", [])]

        alert_type = next(
            (alert_map[c] for c in classes if c in alert_map),
            None
        )

        if not alert_type:
            continue

        block = soup.new_tag("blockquote")
        block["data-docfx-alert"] = alert_type

        # Move children into blockquote
        for child in list(div.children):
            block.append(child)

        div.replace_with(block)


def rewrite_docfx_alerts(markdown: str) -> str:
    """
    Convert semantic alert blockquotes into DocFX markdown.
    """
    def repl(match):
        alert = match.group(1)
        body = match.group(2).strip()
        lines = body.splitlines()

        return "\n".join(
            [f"> [!{alert}]"] + [f"> {line}" for line in lines if line.strip()]
        )

    return re.sub(
        r'>\s*<blockquote data-docfx-alert="(\w+)">\s*(.*?)\s*</blockquote>',
        repl,
        markdown,
        flags=re.S,
    )


# ------------------------------------------------------------
# Code Blocks
# ------------------------------------------------------------

def convert_code_blocks_dom(soup: BeautifulSoup, topic: TopicMetadata):
    """
    Convert <CodeSnippet> elements into <pre><code> blocks.
    """
    for snippet in soup.find_all("codesnippet"):
        lang = (
            snippet.get("DisplayLanguage")
            or snippet.get("Language")
            or "text"
        ).lower()

        code_text = snippet.get_text("\n", strip=True)

        pre = soup.new_tag("pre")
        code = soup.new_tag("code")
        code["class"] = f"language-{lang}"
        code.string = code_text

        pre.append(code)
        snippet.replace_with(pre)


# ------------------------------------------------------------
# Front Matter
# ------------------------------------------------------------

def generate_front_matter(topic: TopicMetadata) -> str:
    lines = [
        "---",
        f'title: "{topic.title}"',
        f"uid: {topic.uid}",
        "ms.topic: reference",
        f"ms.locale: {topic.locale}",
    ]

    if topic.ms_date:
        lines.append(f"ms.date: {topic.ms_date}")

    if topic.canonical_url:
        lines.append(f"canonical_url: {topic.canonical_url}")

    if topic.keywords:
        lines.append("keywords:")
        for kw in sorted(set(topic.keywords)):
            escaped = kw.replace('"', '\\"')
            lines.append(f'  - "{escaped}"')

    lines.append("---")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------
# Metadata Extraction
# ------------------------------------------------------------

def extract_topic_metadata(html_path: Path) -> TopicMetadata:
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "lxml-xml")

    def meta(name: str):
        tag = soup.find("meta", attrs={"name": name})
        return tag["content"].strip() if tag and tag.get("content") else None

    help_id = meta("Microsoft.Help.Id")
    if not help_id:
        raise ValueError(f"No Microsoft.Help.Id in {html_path}")

    uid = help_id.replace("/", ".")
    if "/" in uid:
        raise ValueError(f"Invalid UID: {uid}")

    keywords = [
        tag["content"].strip()
        for tag in soup.find_all("meta", attrs={"name": "Microsoft.Help.Keywords"})
        if tag.get("content")
    ]

    title = meta("Title") or (
        soup.title.string.strip() if soup.title else html_path.stem
    )

    return TopicMetadata(
        help_id=help_id,
        uid=uid,
        title=title,
        locale=meta("Microsoft.Help.Locale") or "en-us",
        topic_version=meta("Microsoft.Help.TopicVersion"),
        canonical_url=meta("OnlineLinkBase"),
        toc_parent=(meta("Microsoft.Help.TocParent") or "").replace("/", ".") or None,
        toc_order=int(meta("Microsoft.Help.TocOrder")) if meta("Microsoft.Help.TocOrder") else None,
        keywords=keywords,
    )


# ------------------------------------------------------------
# Transform Pipeline
# ------------------------------------------------------------

TRANSFORMS: List[DomTransform] = [
    remove_non_content_elements,
    normalize_headings,
    rewrite_mshelp_links_dom,
    rewrite_image_srcs_dom,
    convert_alert_blocks_dom,
    convert_code_blocks_dom,
]


# ------------------------------------------------------------
# Main Conversion Entry Point
# ------------------------------------------------------------

def convert_xhtml_to_markdown(html_path: Path, topic: TopicMetadata) -> str:
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "lxml-xml")

    main = extract_main_body(soup)

    for transform in TRANSFORMS:
        transform(main, topic)

    html = str(main)

    markdown = md(
        html,
        heading_style="ATX",
        bullets="-",
    )

    markdown = rewrite_docfx_alerts(markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = markdown.replace("\u00a0", " ")

    return generate_front_matter(topic) + "\n" + markdown.strip() + "\n"
