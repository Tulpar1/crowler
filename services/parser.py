from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import collections
import re

class CrowlerHTMLParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = set()
        self.text_content = []
        self.in_body = False

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.in_body = True
        elif tag == "a":
            for attr, value in attrs:
                if attr == "href":
                    # Resolve relative URLs to absolute URLs
                    absolute_url = urljoin(self.base_url, value)
                    
                    # Basic validation to ensure it's a HTTP/HTTPS link
                    parsed_url = urlparse(absolute_url)
                    if parsed_url.scheme in ("http", "https"):
                        # Remove fragments for normalization
                        normalized_url = parsed_url._replace(fragment="").geturl()
                        self.links.add(normalized_url)

    def handle_endtag(self, tag):
        if tag == "body":
            self.in_body = False

    def handle_data(self, data):
        # Only collect text if we are typically inside body/visible elements
        # For simplicity, we just collect all non-script/style data
        if self.lasttag not in ("script", "style", "meta", "link"):
            cleaned_data = data.strip()
            if cleaned_data:
                self.text_content.append(cleaned_data)

    def extract_words_and_snippets(self):
        """Extracts word frequencies and context snippets from the collected text."""
        full_text = " ".join(self.text_content)
        lower_text = full_text.lower()
        words = re.finditer(r'\b[a-z0-9]+\b', lower_text)
        word_freqs = collections.Counter()
        snippets = {}
        for match in words:
            word = match.group()
            word_freqs[word] += 1
            if word not in snippets:
                # 40 chars before, 80 after
                start = max(0, match.start() - 40)
                end = min(len(full_text), match.end() + 80)
                snippet = full_text[start:end].replace('\n', ' ')
                # Add ellipsis if cut off
                if start > 0:
                    snippet = "..." + snippet
                if end < len(full_text):
                    snippet = snippet + "..."
                snippets[word] = snippet.strip()
        return word_freqs, snippets

def parse_html(base_url, html_content):
    """
    Parses HTML content to extract absolute links, word frequencies, and context snippets.
    Returns:
        links (set): A set of extracted absolute URLs.
        word_freqs (dict): A dictionary mapping words to their frequency.
        snippets (dict): A dictionary mapping words to a context snippet.
    """
    parser = CrowlerHTMLParser(base_url)
    try:
        # html.parser requires a string, so ensure decoding if necessary
        if isinstance(html_content, bytes):
            html_content = html_content.decode('utf-8', errors='ignore')
        parser.feed(html_content)
    except Exception as e:
        print(f"Error parsing HTML for {base_url}: {e}")
        
    word_freqs, snippets = parser.extract_words_and_snippets()
    return parser.links, word_freqs, snippets
