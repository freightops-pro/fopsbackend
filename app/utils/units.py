"""
Unit Conversion Utilities

Universal Core Requirement: Store all data in metric (km, kg), convert for display only.

Why: 95% of the world uses metric. Only USA, UK, Myanmar use imperial.
Storing in metric prevents rounding errors and allows easier global expansion.
"""

from typing import Literal


UnitSystem = Literal["metric", "imperial"]
DistanceUnit = Literal["kilometers", "miles"]
WeightUnit = Literal["kg", "lbs", "tonnes", "tons"]


# ========== Distance Conversions ==========

def km_to_miles(kilometers: float) -> float:
    """
    Convert kilometers to miles.

    Args:
        kilometers: Distance in kilometers

    Returns:
        Distance in miles

    Example:
        >>> km_to_miles(100)
        62.1371
    """
    return kilometers * 0.621371


def miles_to_km(miles: float) -> float:
    """
    Convert miles to kilometers.

    Args:
        miles: Distance in miles

    Returns:
        Distance in kilometers

    Example:
        >>> miles_to_km(100)
        160.934
    """
    return miles * 1.60934


def convert_distance(
    value: float,
    from_unit: DistanceUnit,
    to_unit: DistanceUnit
) -> float:
    """
    Convert distance between units.

    Args:
        value: Distance value
        from_unit: Source unit ("kilometers" or "miles")
        to_unit: Target unit ("kilometers" or "miles")

    Returns:
        Converted distance

    Example:
        >>> convert_distance(100, "kilometers", "miles")
        62.1371
    """
    if from_unit == to_unit:
        return value

    if from_unit == "kilometers" and to_unit == "miles":
        return km_to_miles(value)
    elif from_unit == "miles" and to_unit == "kilometers":
        return miles_to_km(value)

    raise ValueError(f"Invalid distance units: {from_unit} -> {to_unit}")


# ========== Weight Conversions ==========

def kg_to_lbs(kilograms: float) -> float:
    """
    Convert kilograms to pounds.

    Args:
        kilograms: Weight in kilograms

    Returns:
        Weight in pounds

    Example:
        >>> kg_to_lbs(100)
        220.462
    """
    return kilograms * 2.20462


def lbs_to_kg(pounds: float) -> float:
    """
    Convert pounds to kilograms.

    Args:
        pounds: Weight in pounds

    Returns:
        Weight in kilograms

    Example:
        >>> lbs_to_kg(100)
        45.3592
    """
    return pounds * 0.453592


def tonnes_to_kg(tonnes: float) -> float:
    """Convert metric tonnes to kilograms."""
    return tonnes * 1000


def kg_to_tonnes(kilograms: float) -> float:
    """Convert kilograms to metric tonnes."""
    return kilograms / 1000


def tons_to_lbs(tons: float) -> float:
    """Convert US tons to pounds."""
    return tons * 2000


def lbs_to_tons(pounds: float) -> float:
    """Convert pounds to US tons."""
    return pounds / 2000


def convert_weight(
    value: float,
    from_unit: WeightUnit,
    to_unit: WeightUnit
) -> float:
    """
    Convert weight between units.

    Args:
        value: Weight value
        from_unit: Source unit
        to_unit: Target unit

    Returns:
        Converted weight
    """
    if from_unit == to_unit:
        return value

    # Convert to kg first (base unit)
    if from_unit == "lbs":
        kg = lbs_to_kg(value)
    elif from_unit == "tonnes":
        kg = tonnes_to_kg(value)
    elif from_unit == "tons":
        kg = lbs_to_kg(tons_to_lbs(value))
    else:
        kg = value

    # Convert from kg to target unit
    if to_unit == "lbs":
        return kg_to_lbs(kg)
    elif to_unit == "tonnes":
        return kg_to_tonnes(kg)
    elif to_unit == "tons":
        return lbs_to_tons(kg_to_lbs(kg))
    else:
        return kg


# ========== Region-Based Unit Helpers ==========

def get_distance_unit_for_region(region_code: str) -> DistanceUnit:
    """
    Get preferred distance unit for a region.

    Args:
        region_code: Region code (usa, brazil, eu, etc.)

    Returns:
        Preferred distance unit for that region

    Example:
        >>> get_distance_unit_for_region("usa")
        "miles"
        >>> get_distance_unit_for_region("brazil")
        "kilometers"
    """
    # Only USA, UK, Myanmar use miles. Everyone else uses kilometers.
    imperial_regions = ["usa", "uk"]

    return "miles" if region_code in imperial_regions else "kilometers"


def get_weight_unit_for_region(region_code: str) -> WeightUnit:
    """
    Get preferred weight unit for a region.

    Args:
        region_code: Region code

    Returns:
        Preferred weight unit for that region
    """
    imperial_regions = ["usa", "uk"]

    return "lbs" if region_code in imperial_regions else "kg"


def display_distance(
    distance_km: float,
    region_code: str,
    include_unit: bool = True
) -> str:
    """
    Format distance for display in region's preferred unit.

    Storage: Always kilometers in database
    Display: Convert to miles for USA/UK

    Args:
        distance_km: Distance in kilometers (from database)
        region_code: User's region
        include_unit: Whether to include unit label

    Returns:
        Formatted distance string

    Example:
        >>> display_distance(100, "usa")
        "62.14 miles"
        >>> display_distance(100, "brazil")
        "100.00 kilometers"
    """
    unit = get_distance_unit_for_region(region_code)

    if unit == "miles":
        value = km_to_miles(distance_km)
    else:
        value = distance_km

    formatted = f"{value:.2f}"
    return f"{formatted} {unit}" if include_unit else formatted


def display_weight(
    weight_kg: float,
    region_code: str,
    include_unit: bool = True
) -> str:
    """
    Format weight for display in region's preferred unit.

    Storage: Always kilograms in database
    Display: Convert to lbs for USA/UK

    Args:
        weight_kg: Weight in kilograms (from database)
        region_code: User's region
        include_unit: Whether to include unit label

    Returns:
        Formatted weight string

    Example:
        >>> display_weight(1000, "usa")
        "2,204.62 lbs"
        >>> display_weight(1000, "brazil")
        "1,000.00 kg"
    """
    unit = get_weight_unit_for_region(region_code)

    if unit == "lbs":
        value = kg_to_lbs(weight_kg)
    else:
        value = weight_kg

    # Format with thousands separator
    formatted = f"{value:,.2f}"
    return f"{formatted} {unit}" if include_unit else formatted


# ========== Input Parsing (UI to Database) ==========

def parse_distance_input(
    value: float,
    input_unit: DistanceUnit
) -> float:
    """
    Parse distance input from UI and convert to kilometers for storage.

    Args:
        value: Distance value from user input
        input_unit: Unit user entered (from their region)

    Returns:
        Distance in kilometers (for database storage)

    Example:
        >>> parse_distance_input(100, "miles")  # USA user enters 100 miles
        160.934  # Store as kilometers in database
    """
    if input_unit == "miles":
        return miles_to_km(value)
    return value


def parse_weight_input(
    value: float,
    input_unit: WeightUnit
) -> float:
    """
    Parse weight input from UI and convert to kilograms for storage.

    Args:
        value: Weight value from user input
        input_unit: Unit user entered

    Returns:
        Weight in kilograms (for database storage)
    """
    if input_unit == "lbs":
        return lbs_to_kg(value)
    elif input_unit == "tonnes":
        return tonnes_to_kg(value)
    elif input_unit == "tons":
        return lbs_to_kg(tons_to_lbs(value))
    return value
