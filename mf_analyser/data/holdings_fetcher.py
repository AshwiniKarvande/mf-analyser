"""
Fetcher for Mutual Fund Holdings from Groww.
Groww provides structured JSON in their Next.js __NEXT_DATA__ script tag.
"""

import json
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from mf_analyser.config import AMFI_TO_GROWW_MAPPING

class GrowwHoldingsFetcher:
    BASE_URL = "https://groww.in/mutual-funds"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def fetch_holdings(self, scheme_code: str, custom_slug: Optional[str] = None) -> Dict:
        """
        Fetches holdings for a given AMFI scheme code.
        Uses mapping to find slug, or custom_slug if provided.
        """
        slug = custom_slug or AMFI_TO_GROWW_MAPPING.get(scheme_code)
        if not slug:
            raise ValueError(f"No Groww slug mapping found for scheme code {scheme_code}. Please provide a custom slug.")

        url = f"{self.BASE_URL}/{slug}"
        response = self.session.get(url)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch holdings from {url}. Status: {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")
        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag:
            raise RuntimeError("Could not find __NEXT_DATA__ script tag on Groww page.")

        data = json.loads(script_tag.string)
        
        try:
            page_props = data.get("props", {}).get("pageProps", {})
            
            # Latest Groww Desktop structure: props.pageProps.mfServerSideData
            mf_data = page_props.get("mfServerSideData", {})
            holdings_list = mf_data.get("holdings", [])
            
            if not holdings_list:
                # Fallback path (sometimes Groww uses different props)
                holdings_list = page_props.get("schemeDetails", {}).get("holdings", [])
            
            if not holdings_list:
                # One more fallback (mobile/legacy)
                holdings_list = page_props.get("schemeHistoryPayload", {}).get("holdings", [])

            if not holdings_list:
                raise ValueError("Holdings data not found in Groww JSON.")

            # Map to a clean internal format
            clean_holdings = []
            for h in holdings_list:
                # Use current Desktop fields, but keep fallbacks
                clean_holdings.append({
                    "name": h.get("company_name") or h.get("companyName") or h.get("name"),
                    "sector": h.get("sector_name") or h.get("sectorName") or "Other",
                    "instrument": h.get("instrument_name") or h.get("instrumentName") or "Equity",
                    "weightage": float(h.get("corpus_per") or h.get("portfolioPercent") or 0.0),
                    "market_value": h.get("market_value") or h.get("marketValue")
                })

            # Sort by weightage
            clean_holdings.sort(key=lambda x: x["weightage"], reverse=True)

            return {
                "scheme_code": scheme_code,
                "fund_name": mf_data.get("scheme_name") or mf_data.get("fund_name") or slug,
                "holdings": clean_holdings,
                "as_of_date": mf_data.get("holdings", [{}])[0].get("portfolio_date") or mf_data.get("nav_date") or "",
                "category": mf_data.get("category", ""),
                "total_holdings": len(clean_holdings)
            }

        except Exception as e:
            raise RuntimeError(f"Error parsing Groww holdings JSON: {str(e)}")

def fetch_holdings(scheme_code: str, slug: Optional[str] = None) -> Dict:
    """Convenience function."""
    fetcher = GrowwHoldingsFetcher()
    return fetcher.fetch_holdings(scheme_code, slug)
