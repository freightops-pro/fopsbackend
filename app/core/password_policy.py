"""
Password Policy for Banking-Grade Security.

Requirements:
- Minimum 12 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number
- At least 1 special character
- Cannot contain email or common patterns
"""

import re
from typing import List, Optional


class PasswordPolicy:
    """Enforces strong password requirements."""

    MIN_LENGTH = 12
    COMMON_PASSWORDS = {
        "password", "123456", "12345678", "qwerty", "abc123",
        "monkey", "1234567", "letmein", "trustno1", "dragon",
        "baseball", "iloveyou", "master", "sunshine", "ashley",
        "bailey", "shadow", "123123", "654321", "superman",
        "qazwsx", "michael", "football", "password1", "password123",
    }

    @classmethod
    def validate(cls, password: str, email: Optional[str] = None) -> tuple[bool, List[str]]:
        """
        Validate password against security policy.

        Args:
            password: The password to validate
            email: Optional email to check for inclusion

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if len(password) < cls.MIN_LENGTH:
            errors.append(f"Password must be at least {cls.MIN_LENGTH} characters long")

        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")

        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")

        if not re.search(r"\d", password):
            errors.append("Password must contain at least one number")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'/`~]", password):
            errors.append("Password must contain at least one special character (!@#$%^&*...)")

        if password.lower() in cls.COMMON_PASSWORDS:
            errors.append("Password is too common. Please choose a stronger password")

        if email:
            email_parts = email.lower().split("@")
            username = email_parts[0]
            if len(username) >= 3 and username in password.lower():
                errors.append("Password cannot contain your email address")

        # Check for sequential characters
        if cls._has_sequential_chars(password, 4):
            errors.append("Password cannot contain 4 or more sequential characters (e.g., 1234, abcd)")

        # Check for repeated characters
        if cls._has_repeated_chars(password, 4):
            errors.append("Password cannot contain 4 or more repeated characters (e.g., aaaa)")

        return len(errors) == 0, errors

    @classmethod
    def _has_sequential_chars(cls, password: str, length: int) -> bool:
        """Check for sequential characters like 1234 or abcd."""
        for i in range(len(password) - length + 1):
            substring = password[i:i + length].lower()
            is_sequential = True
            for j in range(len(substring) - 1):
                if ord(substring[j + 1]) != ord(substring[j]) + 1:
                    is_sequential = False
                    break
            if is_sequential:
                return True
        return False

    @classmethod
    def _has_repeated_chars(cls, password: str, length: int) -> bool:
        """Check for repeated characters like aaaa."""
        for i in range(len(password) - length + 1):
            if len(set(password[i:i + length])) == 1:
                return True
        return False

    @classmethod
    def get_strength(cls, password: str) -> dict:
        """Get password strength score and feedback."""
        score = 0
        feedback = []

        # Length scoring
        if len(password) >= 16:
            score += 30
        elif len(password) >= 14:
            score += 25
        elif len(password) >= 12:
            score += 20
        elif len(password) >= 10:
            score += 10
        else:
            feedback.append("Use a longer password")

        # Character variety
        if re.search(r"[A-Z]", password):
            score += 15
        if re.search(r"[a-z]", password):
            score += 15
        if re.search(r"\d", password):
            score += 15
        if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            score += 25

        # Bonus for mixed case throughout
        if re.search(r"[A-Z].*[a-z].*[A-Z]|[a-z].*[A-Z].*[a-z]", password):
            score += 10

        # Determine strength level
        if score >= 90:
            level = "very_strong"
        elif score >= 70:
            level = "strong"
        elif score >= 50:
            level = "moderate"
        elif score >= 30:
            level = "weak"
        else:
            level = "very_weak"

        return {
            "score": min(100, score),
            "level": level,
            "feedback": feedback,
        }


def validate_password(password: str, email: Optional[str] = None) -> tuple[bool, List[str]]:
    """Convenience function to validate password."""
    return PasswordPolicy.validate(password, email)


def get_password_strength(password: str) -> dict:
    """Convenience function to get password strength."""
    return PasswordPolicy.get_strength(password)
