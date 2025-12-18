"""
Tideworks Terminal Scraper Adapter.

Many terminals use Tideworks TOS (Terminal Operating System) which provides
a web interface for container lookup but no public API.

Terminals using Tideworks:
- Terminal 18 (Seattle): https://t18.tideworks.com/fc-T18
- Terminal 5 (Seattle): https://t5s.tideworks.com/fc-T5S
- Shippers Transport: https://sta.tideworks.com/fc-STA
- Pacific Coast Terminal: https://pct.tideworks.com/fc-PCT
- Pier A: https://piera.tideworks.com/fc-PA
- Port of Oakland: https://poha.tideworks.com/fc-POHA
- Port Houston (Bayport): https://bayport.tideworks.com/fc-BPT
- Port Everglades Terminal (Florida): https://pet.tideworks.io/fc-PET-AWS

This adapter uses httpx to fetch and parse the HTML response.
For more reliable scraping, consider using Playwright.

Documentation: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/terminal-18.html
"""

import httpx
import re
from datetime import datetime
from typing import Optional, List, Dict
from html.parser import HTMLParser

from app.schemas.port import (
    ContainerCharges,
    ContainerDates,
    ContainerDetails,
    ContainerLocation,
    ContainerTrackingResponse,
    VesselInfo,
)
from app.services.port.adapters.base_adapter import (
    PortAdapter,
    PortAdapterError,
    PortAuthenticationError,
    PortNotFoundError,
)


class TideworksTableParser(HTMLParser):
    """Parse Tideworks container search results table."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_row = []
        self.rows = []
        self.headers = []
        self.in_header = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            attrs_dict = dict(attrs)
            if "results" in attrs_dict.get("class", "") or "container" in attrs_dict.get("id", ""):
                self.in_table = True
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag == "th" and self.in_row:
            self.in_header = True
            self.in_cell = True
        elif tag == "td" and self.in_row:
            self.in_cell = True

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if self.headers and self.current_row:
                self.rows.append(self.current_row)
            elif self.in_header and self.current_row:
                self.headers = self.current_row
                self.in_header = False
        elif tag in ("td", "th"):
            self.in_cell = False

    def handle_data(self, data):
        if self.in_cell:
            self.current_row.append(data.strip())


class TideworksScraper(PortAdapter):
    """
    Scraper adapter for Tideworks-based terminals.

    Tideworks terminals have a consistent web interface for container lookup.
    This scraper fetches and parses the HTML response.

    Note: Web scraping is fragile and may break if the site changes.
    Consider using this as a fallback when no API is available.
    """

    # Known Tideworks terminal URLs
    TERMINAL_URLS = {
        # Seattle
        "T18": "https://t18.tideworks.com/fc-T18",
        "TERMINAL18": "https://t18.tideworks.com/fc-T18",
        "T5": "https://t5s.tideworks.com/fc-T5S",
        "TERMINAL5": "https://t5s.tideworks.com/fc-T5S",
        # Oakland area
        "STA": "https://sta.tideworks.com/fc-STA",
        "SHIPPERS": "https://sta.tideworks.com/fc-STA",
        # Long Beach
        "PCT": "https://pct.tideworks.com/fc-PCT",
        # Houston
        "POHA": "https://poha.tideworks.com/fc-POHA",
        "BAYPORT": "https://bayport.tideworks.com/fc-BPT",
        "BPT": "https://bayport.tideworks.com/fc-BPT",
        # Pier A (Long Beach)
        "PIERA": "https://piera.tideworks.com/fc-PA",
        "PA": "https://piera.tideworks.com/fc-PA",
        # Florida - Port Everglades
        "PET": "https://pet.tideworks.io/fc-PET-AWS",
        "PORTEVERGLADES": "https://pet.tideworks.io/fc-PET-AWS",
        "EVERGLADES": "https://pet.tideworks.io/fc-PET-AWS",
    }

    # Port code to terminal mapping
    PORT_TERMINALS = {
        "USSEA": ["T18", "T5"],  # Seattle
        "USOAK": ["STA"],  # Oakland
        "USLGB": ["PCT", "PIERA"],  # Long Beach
        "USHOU": ["POHA", "BAYPORT"],  # Houston
        "USPEF": ["PET"],  # Port Everglades, Florida
    }

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)
        # Some terminals require login
        self.username = self.credentials.get("username") if self.credentials else None
        self.password = self.credentials.get("password") if self.credentials else None

    def _get_terminal_url(self, terminal: str) -> str:
        """Get Tideworks URL for terminal code."""
        terminal_upper = terminal.upper().replace(" ", "").replace("-", "")
        url = self.TERMINAL_URLS.get(terminal_upper)
        if not url:
            raise PortAdapterError(f"Unknown Tideworks terminal: {terminal}")
        return url

    async def _fetch_container_data(
        self,
        terminal_url: str,
        container_numbers: List[str],
    ) -> str:
        """Fetch container search results from Tideworks."""
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                # First get the search page to get any CSRF tokens
                search_url = f"{terminal_url}/default.do"
                page_response = await client.get(search_url, timeout=30.0)

                # Build search request
                containers_str = ",".join(container_numbers)
                search_data = {
                    "searchBy": "CONTAINER",
                    "numbers": containers_str,
                }

                # Submit search
                result_response = await client.post(
                    f"{terminal_url}/findcontainer.do",
                    data=search_data,
                    timeout=30.0,
                )
                result_response.raise_for_status()
                return result_response.text

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError("Tideworks login required")
                raise PortAdapterError(f"Failed to fetch data: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error fetching container data: {str(e)}")

    def _parse_container_table(self, html: str, container_number: str) -> Optional[Dict]:
        """Parse container data from HTML table."""
        parser = TideworksTableParser()
        parser.feed(html)

        if not parser.headers or not parser.rows:
            return None

        # Find the row for our container
        container_idx = None
        for i, header in enumerate(parser.headers):
            if "container" in header.lower() or "unit" in header.lower():
                container_idx = i
                break

        if container_idx is None:
            container_idx = 0  # Assume first column

        for row in parser.rows:
            if len(row) > container_idx:
                if container_number.upper() in row[container_idx].upper():
                    # Build data dict from headers and row
                    data = {}
                    for i, header in enumerate(parser.headers):
                        if i < len(row):
                            data[header.lower().replace(" ", "_")] = row[i]
                    return data

        return None

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """
        Track container via Tideworks web scraping.

        Tries all terminals for the given port.
        """
        terminals = self.PORT_TERMINALS.get(port_code.upper(), [])

        if not terminals:
            # Try to use port_code as terminal code
            if port_code.upper() in self.TERMINAL_URLS:
                terminals = [port_code.upper()]
            else:
                raise PortAdapterError(f"No Tideworks terminals known for port: {port_code}")

        last_error = None
        for terminal in terminals:
            try:
                terminal_url = self._get_terminal_url(terminal)
                html = await self._fetch_container_data(terminal_url, [container_number])
                data = self._parse_container_table(html, container_number)

                if data:
                    return self._build_tracking_response(container_number, port_code, terminal, data)

            except PortAdapterError as e:
                last_error = e
                continue
            except Exception as e:
                last_error = PortAdapterError(str(e))
                continue

        if last_error:
            raise last_error
        raise PortNotFoundError(f"Container {container_number} not found at {port_code}")

    def _build_tracking_response(
        self,
        container_number: str,
        port_code: str,
        terminal: str,
        data: Dict,
    ) -> ContainerTrackingResponse:
        """Build ContainerTrackingResponse from parsed data."""

        # Map common Tideworks field names
        status = data.get("status") or data.get("category") or data.get("freight_kind", "UNKNOWN")
        status = self._map_tideworks_status(status)

        # Location
        location = ContainerLocation(
            terminal=terminal,
            yard_location=data.get("location") or data.get("position") or data.get("yard_location"),
            port=port_code,
            country="US",
            timestamp=self._parse_timestamp(data.get("last_move") or data.get("time_in")),
        )

        # Vessel info
        vessel = None
        vessel_name = data.get("vessel") or data.get("vessel_name") or data.get("inbound_vessel")
        if vessel_name:
            vessel = VesselInfo(
                name=vessel_name,
                voyage=data.get("voyage") or data.get("in_voyage"),
                eta=self._parse_timestamp(data.get("eta")),
            )

        # Dates
        dates = ContainerDates(
            discharge_date=self._parse_timestamp(data.get("discharge") or data.get("discharge_date")),
            last_free_day=self._parse_timestamp(data.get("lfd") or data.get("last_free_day")),
            ingate_timestamp=self._parse_timestamp(data.get("time_in") or data.get("in_time")),
            outgate_timestamp=self._parse_timestamp(data.get("time_out") or data.get("out_time")),
        )

        # Container details
        container_details = ContainerDetails(
            size=data.get("size") or data.get("length"),
            type=data.get("type") or data.get("equipment_type"),
            weight=self._parse_weight(data.get("weight") or data.get("gross_weight")),
            shipping_line=data.get("line") or data.get("line_operator") or data.get("ssl"),
        )

        # Holds
        holds = []
        for key in ["holds", "hold", "stop_flags"]:
            if key in data and data[key]:
                hold_val = data[key]
                if isinstance(hold_val, str):
                    holds.extend([h.strip() for h in hold_val.split(",") if h.strip()])

        # Check availability
        avail = data.get("available") or data.get("available_for_pickup") or data.get("avail")
        is_available = avail and avail.lower() in ("yes", "y", "true", "available")

        if is_available and not holds:
            status = "AVAILABLE"

        return self.normalize_tracking_response(
            container_number=container_number,
            port_code=port_code,
            status=status,
            location=location,
            vessel=vessel,
            dates=dates,
            container_details=container_details,
            holds=holds,
            terminal=terminal,
            raw_data=data,
        )

    def _map_tideworks_status(self, status: str) -> str:
        """Map Tideworks status to normalized status."""
        status_lower = status.lower()

        if "yard" in status_lower or "on terminal" in status_lower:
            return "IN_YARD"
        elif "inbound" in status_lower or "advised" in status_lower:
            return "ADVISED"
        elif "discharg" in status_lower:
            return "DISCHARGED"
        elif "available" in status_lower or "released" in status_lower:
            return "AVAILABLE"
        elif "out" in status_lower or "departed" in status_lower:
            return "DEPARTED"
        elif "hold" in status_lower:
            return "ON_HOLD"
        elif "import" in status_lower or "imprt" in status_lower:
            return "IN_YARD"
        elif "export" in status_lower or "exprt" in status_lower:
            return "EXPORT"

        return status.upper() or "UNKNOWN"

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse various timestamp formats."""
        if not timestamp_str:
            return None

        # Common formats
        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def _parse_weight(self, weight_str: Optional[str]) -> Optional[float]:
        """Parse weight string to float."""
        if not weight_str:
            return None
        try:
            # Remove units and commas
            weight_clean = re.sub(r"[^\d.]", "", str(weight_str))
            return float(weight_clean) if weight_clean else None
        except (ValueError, TypeError):
            return None

    async def get_container_events(
        self, container_number: str, port_code: str, since: Optional[datetime] = None
    ) -> list[dict]:
        """Tideworks doesn't provide event history via web interface."""
        return []

    async def get_vessel_schedule(
        self, vessel_name: Optional[str] = None, port_code: Optional[str] = None
    ) -> list[dict]:
        """Tideworks vessel schedule would require additional scraping."""
        return []

    async def test_connection(self) -> bool:
        """Test connection by fetching a terminal page."""
        try:
            # Try first terminal
            first_terminal = list(self.TERMINAL_URLS.keys())[0]
            url = self.TERMINAL_URLS[first_terminal]
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/default.do", timeout=10.0)
                return response.status_code == 200
        except Exception:
            return False
