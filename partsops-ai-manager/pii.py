"""
PartsOps AI Manager v3 — PII Masking Module
All PII must be masked before entering the agent/LLM layer.
"""
import re
from typing import Optional


def mask_phone(phone: str) -> str:
    """Mask phone number, keeping country code and last 4 digits.
    +7-912-345-6789 → +7-***-***-6789
    """
    if not phone:
        return phone
    digits_only = re.sub(r"\D", "", phone)
    if len(digits_only) >= 7:
        visible_suffix = digits_only[-4:]
        visible_prefix = digits_only[:2]
        masked = f"+{visible_prefix[0]}-***-***-{visible_suffix}"
        return masked
    return "***"


def mask_email(email: str) -> str:
    """Mask email, keeping first 2 chars and domain TLD.
    john.doe@company.com → jo***@***.com
    """
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    masked_local = local[:2] + "***" if len(local) > 2 else "***"
    domain_parts = domain.split(".")
    tld = domain_parts[-1] if domain_parts else ""
    masked_domain = f"***.{tld}"
    return f"{masked_local}@{masked_domain}"


def mask_vin(vin: str) -> str:
    """Mask VIN, showing only last 6 characters.
    WBA3C3C50EF123456 → ***-EF123456
    """
    if not vin:
        return vin
    vin_clean = re.sub(r"\s", "", vin).upper()
    if len(vin_clean) >= 6:
        return f"***{vin_clean[-6:]}"
    return "***"


def mask_name(name: str) -> str:
    """Mask customer name for logging.
    Ivan Petrov → Ivan P***
    """
    if not name:
        return name
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1][0]}***"
    if parts:
        return f"{parts[0][:2]}***"
    return "***"


def mask_request_for_agent(raw_data: dict) -> dict:
    """
    Create a PII-safe copy of a request dict for use in agent/LLM layer.
    Masks phone, email, VIN, name.
    """
    safe = dict(raw_data)
    if safe.get("customer_phone"):
        safe["customer_phone"] = mask_phone(safe["customer_phone"])
    if safe.get("customer_email"):
        safe["customer_email"] = mask_email(safe["customer_email"])
    if safe.get("vehicle_vin"):
        safe["vehicle_vin"] = mask_vin(safe["vehicle_vin"])
    if safe.get("customer_name"):
        safe["customer_name"] = mask_name(safe["customer_name"])
    return safe


def mask_for_log(text: str) -> str:
    """
    Scan a text string and redact embedded phone numbers, emails, VINs.
    Suitable for log sanitization.
    """
    # Mask phone patterns
    text = re.sub(
        r"\+?[78]\s?[\-\(]?\d{3}[\-\)]?\s?\d{3}[\-\s]?\d{2}[\-\s]?\d{2}",
        "[ТЕЛЕФОН_СКРЫТ]",
        text,
    )
    # Mask email patterns
    text = re.sub(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        "[EMAIL_СКРЫТ]",
        text,
    )
    # Mask VIN patterns (17 alphanumeric, no I/O/Q)
    text = re.sub(
        r"\b[A-HJ-NPR-Z0-9]{17}\b",
        "[VIN_СКРЫТ]",
        text,
    )
    return text


# WMI Offline Decoder
WMI_MAP = {
    "WBA": "BMW",
    "WAU": "Audi",
    "ZFA": "Fiat",
    "JTD": "Toyota",
    "WDC": "Mercedes-Benz",
    "WP0": "Porsche",
    "1GN": "Chevrolet",
    "1G6": "Cadillac",
    "1HG": "Honda",
    "JHM": "Honda",
    "JT2": "Toyota",
    "JT3": "Toyota",
    "JT4": "Toyota",
    "JT5": "Toyota",
    "SAJ": "Jaguar",
    "SAL": "Land Rover",
    "SCA": "Rolls-Royce",
    "TRU": "Audi",
    "VF1": "Renault",
    "VF3": "Peugeot",
    "VF7": "Citroen",
    "VSS": "SEAT",
    "WVW": "Volkswagen",
    "WVG": "Volkswagen",
    "ZHW": "Lamborghini",
    "ZAM": "Maserati",
    "ZAR": "Alfa Romeo",
}

def decode_vin_offline(vin: str) -> dict:
    if not vin or len(vin) != 17:
        return {"make": "Unknown", "model": "Unknown", "year": "Unknown", "vin_validity": "invalid"}
    
    wmi = vin[:3]
    make = WMI_MAP.get(wmi, "Unknown")
    
    year_map = {
        'A': '2010', 'B': '2011', 'C': '2012', 'D': '2013', 'E': '2014', 'F': '2015',
        'G': '2016', 'H': '2017', 'J': '2018', 'K': '2019', 'L': '2020', 'M': '2021',
        'N': '2022', 'P': '2023', 'R': '2024', 'S': '2025', 'T': '2026', 'V': '2027',
        'W': '2028', 'X': '2029', 'Y': '2030', '1': '2001', '2': '2002', '3': '2003',
        '4': '2004', '5': '2005', '6': '2006', '7': '2007', '8': '2008', '9': '2009'
    }
    
    year_char = vin[9].upper()
    year = year_map.get(year_char, "Unknown")
    
    model = "Unknown"
    
    return {
        "make": make,
        "model": model,
        "year": year,
        "vin_validity": "valid"
    }

def secure_pre_parse(text: str) -> dict:
    """
    Extracts PII (VIN, phone, email), decodes VIN offline,
    and returns masked text, a PII map, and vehicle context.
    """
    pii_map = {}
    masked_text = text
    
    vin_pattern = r"\b[A-HJ-NPR-Z0-9]{17}\b"
    phone_pattern = r"\+?[78]\s?[\-\(]?\d{3}[\-\)]?\s?\d{3}[\-\s]?\d{2}[\-\s]?\d{2}"
    email_pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    
    vins = re.findall(vin_pattern, masked_text)
    vehicle_context = {"vin": None, "make": "Unknown", "model": "Unknown", "year": "Unknown", "vin_validity": "invalid"}
    for vin in set(vins):
        pii_map["[VIN_СКРЫТ]"] = vin
        vehicle_context = decode_vin_offline(vin)
        vehicle_context["vin"] = vin
        masked_text = re.sub(r"\b" + vin + r"\b", "[VIN_СКРЫТ]", masked_text)
        
    phones = re.findall(phone_pattern, masked_text)
    for phone in set(phones):
        pii_map["[ТЕЛЕФОН_СКРЫТ]"] = phone
        masked_text = masked_text.replace(phone, "[ТЕЛЕФОН_СКРЫТ]")
        
    emails = re.findall(email_pattern, masked_text)
    for email in set(emails):
        pii_map["[EMAIL_СКРЫТ]"] = email
        masked_text = masked_text.replace(email, "[EMAIL_СКРЫТ]")

    return {
        "masked_text": masked_text,
        "pii_map": pii_map,
        "vehicle_context": vehicle_context
    }
