"""Layer 1: Identity Normalizer — Variant and Dork Generator."""

from datetime import datetime
import re
from .platform_catalog import get_dork_platforms, get_priority_search_domains


class SearchBundle:
    """Container for all generated search variants and dork queries."""

    def __init__(self, original_name, email=None, username=None, phone=None, address=None):
        self.original_name = original_name
        self.email = email
        self.username = username
        self.phone = phone
        self.address = address
        self.username_variants = []
        self.dork_queries = []
        self.search_queries = []


class IdentityNormalizer:
    """Generates username variants and search dorks from identity input."""

    # Common separators used in usernames
    SEPARATORS = ["", ".", "_", "-"]

    # Common suffixes people append
    COMMON_SUFFIXES = ["01", "99", "123", "007", "x", "dev", "official", "real"]

    @staticmethod
    def clean_name(name):
        """Normalize a name string: lowercase, strip, remove special chars."""
        name = name.strip().lower()
        name = re.sub(r"[^a-z\s]", "", name)
        return name

    @classmethod
    def generate_username_variants(cls, name, email=None, username=None):
        """Generate all plausible username permutations from a name."""
        variants = []
        seen = set()

        def add_variant(value):
            value = (value or "").strip().lower()
            if not value or value in seen:
                return
            seen.add(value)
            variants.append(value)

        cleaned = cls.clean_name(name)
        parts = cleaned.split()

        if not parts:
            return variants

        first = parts[0]
        last = parts[-1] if len(parts) > 1 else ""
        middle_parts = parts[1:-1] if len(parts) > 2 else []
        middle_initials = [m[0] for m in middle_parts]

        # --- Core patterns ---
        base_patterns = []

        if username:
            uname = username.strip().lower()
            add_variant(uname)
            add_variant(re.sub(r"[._-]", "", uname))

        if email and "@" in email:
            email_user = email.split("@")[0].lower()
            add_variant(email_user)
            add_variant(re.sub(r"\d+", "", email_user))

        if last:
            base_patterns.extend([
                f"{first}{last}",           # parthpakhare
                f"{last}{first}",           # pakhareparth
                f"{first[0]}{last}",        # ppakhare
                f"{first}{last[0]}",        # parthp
                f"{last}{first[0]}",        # pakharep
                f"{first[0]}{last[0]}",     # pp
            ])

            # With separators
            for sep in cls.SEPARATORS:
                if sep:
                    base_patterns.extend([
                        f"{first}{sep}{last}",    # parth.pakhare
                        f"{last}{sep}{first}",    # pakhare.parth
                        f"{first[0]}{sep}{last}", # p.pakhare
                    ])

            # With middle initials
            for mi in middle_initials:
                base_patterns.extend([
                    f"{first}{mi}{last}",
                    f"{first[0]}{mi}{last}",
                ])
        else:
            base_patterns.append(first)

        for pattern in base_patterns:
            add_variant(pattern)

        for pattern in list(base_patterns)[:8]:
            for suffix in cls.COMMON_SUFFIXES[:4]:
                add_variant(f"{pattern}{suffix}")

        return variants

    @classmethod
    def generate_username_variants_multi(cls, name, email=None, username=None):
        """Generate username variants, supporting comma-separated usernames."""
        if username and "," in username:
            all_variants = []
            seen = set()
            for uname in username.split(","):
                uname = uname.strip()
                if not uname:
                    continue
                for v in cls.generate_username_variants(name, email, uname):
                    if v not in seen:
                        seen.add(v)
                        all_variants.append(v)
            # Also generate base name-only variants
            for v in cls.generate_username_variants(name, email, None):
                if v not in seen:
                    seen.add(v)
                    all_variants.append(v)
            return all_variants
        return cls.generate_username_variants(name, email, username)

    @classmethod
    def generate_dork_queries(cls, name, email=None, username=None):
        """Generate Google-style dork queries for discovery."""
        dorks = []
        # Name-based dorks
        for platform, category in get_dork_platforms():
            dorks.append({
                "query": f'site:{platform} "{name}"',
                "platform": platform.split(".")[0] if "." in platform else platform,
                "category": category,
            })

        # Email-based dorks
        if email:
            dorks.append({"query": f'"{email}"', "platform": "web", "category": "general"})
            dorks.append({"query": f'"{email}" site:github.com', "platform": "github", "category": "developer"})

        # Contact exposure dorks
        dorks.append({"query": f'"{name}" email OR contact OR phone', "platform": "web", "category": "exposure"})
        dorks.append({"query": f'"{name}" resume OR cv ext:pdf', "platform": "web", "category": "documents"})

        return dorks

    @classmethod
    def generate_search_queries(cls, name, email=None, username=None):
        """Generate simple search queries for SearxNG."""
        from datetime import datetime
        current_year = datetime.now().year

        queries = [f'"{name}"']

        if email:
            queries.append(f'"{email}"')

        if username:
            queries.append(f'"{username}"')
            for domain in get_priority_search_domains(limit=4):
                queries.append(f'site:{domain} "{username}"')

        # Combination queries
        if email and name:
            queries.append(f'"{name}" "{email}"')

        if username and name:
            queries.append(f'"{name}" "{username}"')

        # === Real-Time Recency Dorks ===
        # Force search engines to surface results from this year / recent period
        queries.append(f'"{name}" after:2025-01-01')
        queries.append(
            f'"{name}" site:linkedin.com OR site:github.com OR site:twitter.com "{current_year}"'
        )
        queries.append(f'site:x.com "{name}" "{current_year}"')

        return queries

    @classmethod
    def generate_search_queries_multi(cls, name, email=None, username=None, phone=None, address=None):
        """Generate search queries supporting multiple usernames, phones, and address."""
        queries = cls.generate_search_queries(name, email, username)
        seen = set(queries)

        def _add(q):
            if q not in seen:
                seen.add(q)
                queries.append(q)

        # Handle comma-separated usernames
        if username and "," in username:
            for uname in username.split(","):
                uname = uname.strip()
                if not uname:
                    continue
                _add(f'"{uname}"')
                for domain in get_priority_search_domains(limit=4):
                    _add(f'site:{domain} "{uname}"')
                if name:
                    _add(f'"{name}" "{uname}"')

        # Handle comma-separated phones
        if phone:
            for p in phone.split(","):
                p = p.strip()
                if not p:
                    continue
                _add(f'"{p}"')
                _add(f'"{name}" "{p}"')

        # Address-based dorks
        if address:
            _add(f'"{name}" "{address}"')
            _add(f'"{address}"')
            _add(f'"{name}" "{address}" site:linkedin.com OR site:facebook.com')

        return queries

    @classmethod
    def create_search_bundle(cls, name, email=None, username=None, phone=None, address=None):
        """Create a complete SearchBundle from identity input."""
        bundle = SearchBundle(name, email, username, phone, address)
        bundle.username_variants = cls.generate_username_variants_multi(name, email, username)
        bundle.dork_queries = cls.generate_dork_queries(name, email, username)
        bundle.search_queries = cls.generate_search_queries_multi(name, email, username, phone, address)
        return bundle
