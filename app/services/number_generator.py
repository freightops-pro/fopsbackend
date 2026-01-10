"""
Number Generation Service

Generates sequential numbers for invoices, loads, etc. with customizable formats.
Supports tokens like {YEAR}, {MONTH}, {NUMBER}, {CUSTOMER_PREFIX}, etc.
"""

import re
from datetime import datetime
from typing import Optional


class NumberGenerator:
    """Service for generating formatted sequential numbers."""

    @staticmethod
    def generate(
        format_template: str,
        sequence_number: int,
        customer_name: Optional[str] = None,
        date: Optional[datetime] = None,
    ) -> str:
        """
        Generate a formatted number based on template and sequence.

        Args:
            format_template: Template string with tokens (e.g., "INV-{YEAR}-{NUMBER:05}")
            sequence_number: The sequential number to use
            customer_name: Optional customer name for {CUSTOMER_PREFIX} token
            date: Optional date to use (defaults to current date)

        Returns:
            Formatted number string (e.g., "INV-2024-00001")

        Supported tokens:
            {YEAR}            - Current year (e.g., 2024)
            {YEAR:2}          - Last 2 digits of year (e.g., 24)
            {MONTH}           - Current month zero-padded (e.g., 01-12)
            {DAY}             - Current day zero-padded (e.g., 01-31)
            {NUMBER}          - Sequential number
            {NUMBER:05}       - Sequential number zero-padded to 5 digits
            {CUSTOMER_PREFIX} - First 3 uppercase letters of customer name
            {CUSTOMER_PREFIX:4} - First 4 uppercase letters of customer name
        """
        if not date:
            date = datetime.utcnow()

        result = format_template

        # Replace date tokens
        result = result.replace("{YEAR}", str(date.year))
        result = re.sub(r'\{YEAR:(\d+)\}', lambda m: str(date.year)[-int(m.group(1)):], result)
        result = result.replace("{MONTH}", f"{date.month:02d}")
        result = result.replace("{DAY}", f"{date.day:02d}")

        # Replace number token with optional padding
        number_pattern = r'\{NUMBER(?::(\d+))?\}'
        def replace_number(match):
            padding = int(match.group(1)) if match.group(1) else 0
            if padding > 0:
                return f"{sequence_number:0{padding}d}"
            return str(sequence_number)

        result = re.sub(number_pattern, replace_number, result)

        # Replace customer prefix token
        if customer_name:
            # Extract length if specified, default to 3
            prefix_pattern = r'\{CUSTOMER_PREFIX(?::(\d+))?\}'
            def replace_prefix(match):
                length = int(match.group(1)) if match.group(1) else 3
                # Remove special characters and get first N letters
                clean_name = re.sub(r'[^A-Za-z]', '', customer_name)
                return clean_name[:length].upper() if clean_name else "CUST"

            result = re.sub(prefix_pattern, replace_prefix, result)
        else:
            # If no customer name provided, remove the token or replace with default
            result = re.sub(r'\{CUSTOMER_PREFIX(?::(\d+))?\}', 'CUST', result)

        return result

    @staticmethod
    def preview_format(
        format_template: str,
        example_number: int = 1,
        customer_name: str = "ACME Corporation",
    ) -> str:
        """
        Generate a preview of what the format will look like.

        Args:
            format_template: Template string
            example_number: Example sequence number (default 1)
            customer_name: Example customer name (default "ACME Corporation")

        Returns:
            Example formatted number
        """
        return NumberGenerator.generate(
            format_template,
            example_number,
            customer_name=customer_name,
        )

    @staticmethod
    def validate_format(format_template: str) -> tuple[bool, Optional[str]]:
        """
        Validate a format template.

        Args:
            format_template: Template string to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not format_template or not isinstance(format_template, str):
            return False, "Format template cannot be empty"

        if len(format_template) > 100:
            return False, "Format template is too long (max 100 characters)"

        # Check for {NUMBER} token - it's required
        if "{NUMBER" not in format_template:
            return False, "Format must contain {NUMBER} token"

        # Check for balanced braces
        if format_template.count("{") != format_template.count("}"):
            return False, "Unbalanced braces in format template"

        # Check for valid tokens
        valid_tokens = [
            r'\{YEAR(?::\d+)?\}',
            r'\{MONTH\}',
            r'\{DAY\}',
            r'\{NUMBER(?::\d+)?\}',
            r'\{CUSTOMER_PREFIX(?::\d+)?\}',
        ]

        # Extract all tokens from template
        tokens = re.findall(r'\{[^}]+\}', format_template)

        for token in tokens:
            # Check if token matches any valid pattern
            is_valid_token = any(re.match(pattern, token) for pattern in valid_tokens)
            if not is_valid_token:
                return False, f"Invalid token: {token}"

        return True, None
