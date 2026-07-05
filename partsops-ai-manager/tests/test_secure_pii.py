"""
Tests for Secure PII & VIN Layer.
Ensures raw VIN and PII do not leak to the agent/LLM layer,
and offline decoding works correctly.
"""

from pii import secure_pre_parse, decode_vin_offline

def test_offline_vin_decoding_bmw():
    vin = "WBA3C3C50EF123456" # BMW WBA
    result = decode_vin_offline(vin)
    assert result["make"] == "BMW"
    assert result["vin_validity"] == "valid"

def test_offline_vin_decoding_invalid_length():
    vin = "SHORTVIN"
    result = decode_vin_offline(vin)
    assert result["vin_validity"] == "invalid"
    assert result["make"] == "Unknown"

def test_secure_pre_parse_masks_vin_and_pii():
    raw_text = "Нужен масляный фильтр и тормозные колодки передние на BMW X5, VIN WBA3C3C50EF123456. Мой телефон +7 912 345 6789, email john@example.com"
    result = secure_pre_parse(raw_text)
    
    masked_text = result["masked_text"]
    
    # Assert raw values are NOT in the masked text
    assert "WBA3C3C50EF123456" not in masked_text
    assert "+7 912 345 6789" not in masked_text
    assert "john@example.com" not in masked_text
    
    # Assert placeholders are IN the masked text
    assert "[VIN_СКРЫТ]" in masked_text
    assert "[ТЕЛЕФОН_СКРЫТ]" in masked_text
    assert "[EMAIL_СКРЫТ]" in masked_text
    
    # Assert pii map has correct values
    assert result["pii_map"]["[VIN_СКРЫТ]"] == "WBA3C3C50EF123456"
    assert result["pii_map"]["[ТЕЛЕФОН_СКРЫТ]"] == "+7 912 345 6789"
    assert result["pii_map"]["[EMAIL_СКРЫТ]"] == "john@example.com"
    
    # Assert offline decoding happened and context was set
    vehicle_context = result["vehicle_context"]
    assert vehicle_context["make"] == "BMW"
    assert vehicle_context["vin_validity"] == "valid"
