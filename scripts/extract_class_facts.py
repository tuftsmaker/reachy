#!/usr/bin/env python3
"""Extract a plain-text digest of the ENT-164 syllabus for the class Q&A demo.

The syllabus page is the single source of truth for the course (see the
ENT-164 repo); this script turns it into the text blob that class_qa.py feeds
to the LLM as context.

Usage:
    python scripts/extract_class_facts.py \
        [--syllabus ~/GitHub/ENT-164/syllabus/index.html] \
        [-o demo/class_facts.md]
"""

import argparse
import os
import re
from datetime import date
from html.parser import HTMLParser

SKIP_TAGS = {"script", "style", "svg", "head", "noscript"}
BLOCK_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "li", "p", "div", "section", "article",
    "tr", "td", "th", "br", "ul", "ol", "table", "header", "footer",
}


class TextExtract(HTMLParser):
    """Very small HTML-to-text converter: block tags become line breaks."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in SKIP_TAGS:
            self.skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text + " ")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--syllabus",
        default="~/GitHub/ENT-164/syllabus/index.html",
        help="path to the ENT-164 syllabus page",
    )
    ap.add_argument("-o", "--output", default="demo/class_facts.md")
    args = ap.parse_args()

    src = os.path.expanduser(args.syllabus)
    html = open(src, encoding="utf-8").read()

    extractor = TextExtract()
    extractor.feed(html)
    text = "".join(extractor.parts)

    # Collapse whitespace: keep paragraph breaks, kill the rest.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    header = (
        "# ENT-164 Intro to Making -- class facts (for the robot Q&A)\n"
        f"_Extracted from the syllabus page on {date.today().isoformat()}._\n\n"
    )
    out = os.path.expanduser(args.output)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(header + text + "\n")

    print(f"wrote {out}: {len(text)} chars from {src}")


if __name__ == "__main__":
    main()
