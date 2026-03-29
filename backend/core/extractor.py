"""Layer 4: Entity Extraction — Emails, phones, handles, and links."""

import re
from urllib.parse import urlparse


# --- Regex Patterns ---

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}",
)

SOCIAL_HANDLE_PATTERN = re.compile(
    r"@([a-zA-Z0-9_]{1,30})",
)

URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+",
)

# Social platform URL patterns for cross-referencing
PLATFORM_URL_PATTERNS = {
    "github": re.compile(r"github\.com/([a-zA-Z0-9\-]+)", re.IGNORECASE),
    "twitter": re.compile(r"(?:twitter|x)\.com/([a-zA-Z0-9_]+)", re.IGNORECASE),
    "linkedin": re.compile(r"linkedin\.com/in/([a-zA-Z0-9\-]+)", re.IGNORECASE),
    "instagram": re.compile(r"instagram\.com/([a-zA-Z0-9_.]+)", re.IGNORECASE),
    "reddit": re.compile(r"reddit\.com/u(?:ser)?/([a-zA-Z0-9_\-]+)", re.IGNORECASE),
    "medium": re.compile(r"medium\.com/@([a-zA-Z0-9._]+)", re.IGNORECASE),
    "youtube": re.compile(r"youtube\.com/@([a-zA-Z0-9_]+)", re.IGNORECASE),
    "facebook": re.compile(r"facebook\.com/([a-zA-Z0-9.]+)", re.IGNORECASE),
    "tiktok": re.compile(r"tiktok\.com/@([a-zA-Z0-9_.]+)", re.IGNORECASE),
    "stackoverflow": re.compile(r"stackoverflow\.com/users/(\d+)", re.IGNORECASE),
}

# Known junk emails to filter out
JUNK_EMAILS = {
    "noreply@github.com", "support@twitter.com", "help@instagram.com",
    "privacy@linkedin.com", "example@example.com", "test@test.com",
    "admin@admin.com", "user@example.com",
}

# Known junk handles to filter
JUNK_HANDLES = {
    "charset", "media", "import", "keyframes", "font", "page",
    "supports", "layer", "container", "scope", "property",
}


class EntitySet:
    """Container for entities extracted from a single page."""

    def __init__(self, url=""):
        self.url = url
        self.emails = set()
        self.phones = set()
        self.handles = set()
        self.linked_urls = set()
        self.platform_usernames = {}  # platform -> username
        self.names_mentioned = set()

    def to_dict(self):
        return {
            "url": self.url,
            "emails": sorted(self.emails),
            "phones": sorted(self.phones),
            "handles": sorted(self.handles),
            "linked_urls": sorted(self.linked_urls),
            "platform_usernames": self.platform_usernames,
        }

    @property
    def total_entities(self):
        return len(self.emails) + len(self.phones) + len(self.handles) + len(self.platform_usernames)


def extract_emails(text):
    """Extract and clean emails from text."""
    found = EMAIL_PATTERN.findall(text)
    cleaned = set()
    for email in found:
        email = email.lower().strip(".")
        if email not in JUNK_EMAILS and not email.endswith(".png") and not email.endswith(".jpg"):
            cleaned.add(email)
    return cleaned


def extract_phones(text):
    """Extract phone numbers from text."""
    found = PHONE_PATTERN.findall(text)
    cleaned = set()
    for phone in found:
        digits = re.sub(r"[^\d+]", "", phone)
        if 7 <= len(digits) <= 15:
            cleaned.add(phone.strip())
    return cleaned


def extract_handles(text):
    """Extract social media handles from text."""
    found = SOCIAL_HANDLE_PATTERN.findall(text)
    cleaned = set()
    for handle in found:
        if handle.lower() not in JUNK_HANDLES and len(handle) > 1:
            cleaned.add(handle)
    return cleaned


def extract_platform_links(text):
    """Extract and identify platform-specific links and usernames."""
    urls = URL_PATTERN.findall(text)
    platform_usernames = {}
    valid_urls = set()

    for url in urls:
        url = url.rstrip(".,;:)'\"]}")
        valid_urls.add(url)
        for platform, pattern in PLATFORM_URL_PATTERNS.items():
            match = pattern.search(url)
            if match:
                username = match.group(1)
                if len(username) > 1 and username.lower() not in {"about", "help", "login", "signup", "search"}:
                    platform_usernames[platform] = username

    return valid_urls, platform_usernames


def extract_entities(text, url=""):
    """Extract all entity types from a text block."""
    entity_set = EntitySet(url=url)
    entity_set.emails = extract_emails(text)
    entity_set.phones = extract_phones(text)
    entity_set.handles = extract_handles(text)
    linked_urls, platform_usernames = extract_platform_links(text)
    entity_set.linked_urls = linked_urls
    entity_set.platform_usernames = platform_usernames

    return entity_set


def extract_from_snippet(snippet, url=""):
    """Extract entities from search engine snippet (lightweight extraction)."""
    entity_set = EntitySet(url=url)
    entity_set.emails = extract_emails(snippet)
    entity_set.phones = extract_phones(snippet)
    entity_set.handles = extract_handles(snippet)
    return entity_set
