"""
Tests: PII Masking Module
"""
import pytest
from pii import mask_phone, mask_email, mask_vin, mask_name, mask_request_for_agent, mask_for_log


class TestPhoneMasking:
    def test_russian_phone_masked(self):
        result = mask_phone("+79123456789")
        assert "6789" in result
        assert "9123" not in result
        assert "***" in result

    def test_phone_with_dashes(self):
        result = mask_phone("+7-912-345-6789")
        assert "6789" in result
        assert "345" not in result

    def test_empty_phone(self):
        assert mask_phone("") == ""

    def test_short_phone_returns_redacted(self):
        result = mask_phone("123")
        assert result == "***"


class TestEmailMasking:
    def test_basic_email(self):
        result = mask_email("john.doe@gmail.com")
        assert "jo***" in result
        assert ".com" in result
        assert "john.doe" not in result
        assert "gmail" not in result

    def test_email_without_at(self):
        result = mask_email("notanemail")
        assert result == "***"

    def test_empty_email(self):
        result = mask_email("")
        assert result == "***"

    def test_short_local_part(self):
        result = mask_email("a@b.ru")
        assert "***" in result
        assert ".ru" in result


class TestVINMasking:
    def test_standard_vin(self):
        result = mask_vin("WBA3C3C50EF123456")
        assert "123456" in result
        assert "WBA3C3C50" not in result
        assert "***" in result

    def test_empty_vin(self):
        assert mask_vin("") == ""

    def test_short_vin(self):
        result = mask_vin("ABC")
        assert result == "***"


class TestNameMasking:
    def test_full_name(self):
        result = mask_name("Иван Петров")
        assert "Иван" in result
        assert "П***" in result
        assert "Петров" not in result

    def test_single_name(self):
        result = mask_name("Иван")
        assert "Ив***" in result

    def test_empty_name(self):
        assert mask_name("") == ""


class TestRequestMasking:
    def test_mask_request_dict(self):
        data = {
            "customer_name": "Иван Петров",
            "customer_phone": "+79123456789",
            "customer_email": "ivan@mail.ru",
            "vehicle_vin": "WBA3C3C50EF123456",
            "text": "Нужны запчасти",
        }
        masked = mask_request_for_agent(data)
        assert "Петров" not in masked["customer_name"]
        assert "9123" not in masked["customer_phone"]
        assert "ivan" not in masked["customer_email"]
        assert "WBA3C3" not in masked["vehicle_vin"]
        # Non-PII fields unchanged
        assert masked["text"] == "Нужны запчасти"


class TestLogMasking:
    def test_phone_in_log(self):
        text = "Клиент +79123456789 запросил детали"
        result = mask_for_log(text)
        assert "79123456789" not in result
        assert "ТЕЛЕФОН_СКРЫТ" in result

    def test_email_in_log(self):
        text = "Отправлено на john.doe@company.com"
        result = mask_for_log(text)
        assert "john.doe@company.com" not in result
        assert "EMAIL_СКРЫТ" in result

    def test_vin_in_log(self):
        # Must be exactly 17 valid VIN chars (no I/O/Q)
        text = "VIN: WBA3C3C50EF123456"
        result = mask_for_log(text)
        assert "WBA3C3C50EF123456" not in result

    def test_clean_text_unchanged(self):
        text = "Тормозные колодки BMW X5, количество 2 шт"
        result = mask_for_log(text)
        assert "Тормозные колодки" in result
