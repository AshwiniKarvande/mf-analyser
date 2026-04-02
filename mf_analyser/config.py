"""
Configuration — paths, cache TTL, and default fund universe.
"""

from pathlib import Path

# ─── Project root ─────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent

# ─── Data cache directories ───────────────────────────────────────────────────
DATA_DIR = ROOT_DIR / "data"
NAV_CACHE_DIR = DATA_DIR / "nav"
AUM_CACHE_DIR = DATA_DIR / "aum"
SCHEME_LIST_CACHE = DATA_DIR / "scheme_codes.csv"

# ─── Cache TTL ────────────────────────────────────────────────────────────────
NAV_CACHE_TTL_HOURS = 24        # Refresh NAV CSV if older than this many hours
SCHEME_LIST_TTL_DAYS = 7        # Refresh scheme list weekly
AUM_CACHE_TTL_DAYS = 90         # AUM is quarterly; rarely changes

# ─── Default fund universe ────────────────────────────────────────────────────
# Scheme codes are for the Direct Growth variant of each fund.
# Use `mfa search <name>` to find/confirm the scheme code for any fund.
DEFAULT_FUNDS: dict[str, dict] = {
    "Mirae Asset Large Cap Fund": {
        "scheme_code": "118989",
        "category": "Large Cap",
        "amc": "Mirae Asset",
        "tags": ["large-cap", "equity"],
    },
    "PPFAS FlexiCap Fund": {
        "scheme_code": "122639",
        "category": "Flexi Cap",
        "amc": "PPFAS",
        "tags": ["flexi-cap", "equity", "value"],
    },
    "ICICI Pru Large Cap Fund": {
        "scheme_code": "120586",
        "category": "Large Cap",
        "amc": "ICICI Prudential",
        "tags": ["large-cap", "equity"],
    },
    "Nippon Multi-Cap Fund": {
        "scheme_code": "118825",
        "category": "Multi Cap",
        "amc": "Nippon India",
        "tags": ["multi-cap", "equity"],
    },
    "Kotak Midcap Fund": {
        "scheme_code": "120465",
        "category": "Mid Cap",
        "amc": "Kotak",
        "tags": ["mid-cap", "equity"],
    },
    "HDFC Small Cap Fund": {
        "scheme_code": "118731",
        "category": "Small Cap",
        "amc": "HDFC",
        "tags": ["small-cap", "equity"],
    },
    "Nippon Small Cap Fund": {
        "scheme_code": "118778",
        "category": "Small Cap",
        "amc": "Nippon India",
        "tags": ["small-cap", "equity"],
    },
    "UTI Nifty 50 Index Fund": {
        "scheme_code": "120716",
        "category": "Index Fund",
        "amc": "UTI",
        "tags": ["index", "nifty-50", "passive"],
    },
    "UTI Nifty Next 50 Index Fund": {
        "scheme_code": "120684",
        "category": "Index Fund",
        "amc": "UTI",
        "tags": ["index", "nifty-next-50", "passive"],
    },
    "ICICI Pru Nifty Bank Index Fund": {
        "scheme_code": "120620",
        "category": "Index Fund",
        "amc": "ICICI Prudential",
        "tags": ["index", "banking", "passive", "sectoral"],
    },
}

# ─── Convenience helpers ──────────────────────────────────────────────────────
FUND_NAME_TO_CODE: dict[str, str] = {
    name: info["scheme_code"] for name, info in DEFAULT_FUNDS.items()
}

FUND_CODE_TO_NAME: dict[str, str] = {
    info["scheme_code"]: name for name, info in DEFAULT_FUNDS.items()
}
