"""
Tests: Pricing & Margin Guard
"""
import pytest
from pricing import compute_price, check_margin_guard, PricingContext, MARGIN_POLICY


class TestMarginGuard:
    def test_default_margin_ok(self):
        result = check_margin_guard(purchase_price=1000.0, sale_price=1200.0)
        assert result["passed"] is True
        assert result["margin"] == pytest.approx(0.20, abs=0.01)

    def test_default_margin_fail(self):
        result = check_margin_guard(purchase_price=1000.0, sale_price=1050.0)
        assert result["passed"] is False
        assert result["violation"] is not None and "12.0%" in result["violation"]

    def test_non_returnable_policy(self):
        # Non-returnable requires 18% min
        result = check_margin_guard(purchase_price=1000.0, sale_price=1150.0, policy_key="non_returnable")
        assert result["passed"] is False  # 15% < 18%

        result2 = check_margin_guard(purchase_price=1000.0, sale_price=1200.0, policy_key="non_returnable")
        assert result2["passed"] is True  # 20% > 18%

    def test_original_bmw_policy(self):
        # BMW original only needs 10%
        result = check_margin_guard(purchase_price=10000.0, sale_price=11000.0, policy_key="original_bmw")
        assert result["passed"] is True  # 10% == 10%

    def test_zero_purchase_price(self):
        result = check_margin_guard(purchase_price=0, sale_price=100)
        assert result["passed"] is False

    def test_high_risk_supplier_policy(self):
        result = check_margin_guard(purchase_price=1000.0, sale_price=1150.0, policy_key="high_risk_supplier")
        assert result["passed"] is False  # 15% < 20%
        result2 = check_margin_guard(purchase_price=1000.0, sale_price=1250.0, policy_key="high_risk_supplier")
        assert result2["passed"] is True  # 25% > 20%


class TestPricingFormula:
    def _default_ctx(self, purchase_price=1000.0, **kwargs) -> PricingContext:
        return PricingContext(purchase_price=purchase_price, **kwargs)

    def test_basic_pricing(self):
        ctx = self._default_ctx(1000.0)
        result = compute_price(ctx)
        assert result.purchase_price == 1000.0
        assert result.client_price > 1000.0
        assert result.margin_policy_passed is True
        assert result.tax_amount > 0

    def test_urgency_buffer_applied(self):
        ctx_normal = self._default_ctx(1000.0, urgency_level="normal")
        ctx_urgent = self._default_ctx(1000.0, urgency_level="urgent")
        assert compute_price(ctx_urgent).urgency_buffer > compute_price(ctx_normal).urgency_buffer

    def test_low_reliability_adds_risk_buffer(self):
        ctx_high = self._default_ctx(1000.0, supplier_reliability_score=0.95)
        ctx_low = self._default_ctx(1000.0, supplier_reliability_score=0.60)
        assert compute_price(ctx_low).risk_buffer > compute_price(ctx_high).risk_buffer

    def test_non_returnable_min_margin_higher(self):
        ctx = self._default_ctx(1000.0, is_non_returnable=True)
        result = compute_price(ctx)
        assert result.policy_min_margin == MARGIN_POLICY["non_returnable"]

    def test_price_anomaly_detected(self):
        ctx = self._default_ctx(
            1000.0,
            historical_median_price_90d=600.0,  # 67% deviation
        )
        result = compute_price(ctx)
        assert result.price_anomaly_detected is True
        assert result.price_deviation > 0.20

    def test_no_price_anomaly(self):
        ctx = self._default_ctx(
            1000.0,
            historical_median_price_90d=1050.0,  # 5% deviation
        )
        result = compute_price(ctx)
        assert result.price_anomaly_detected is False

    def test_auto_approve_allowed_when_clean(self):
        ctx = self._default_ctx(
            1000.0,
            supplier_reliability_score=0.90,
            historical_median_price_90d=980.0,
        )
        result = compute_price(ctx)
        assert result.auto_approve_allowed is True

    def test_auto_approve_blocked_on_anomaly(self):
        ctx = self._default_ctx(
            1000.0,
            supplier_reliability_score=0.90,
            historical_median_price_90d=500.0,  # huge anomaly
        )
        result = compute_price(ctx)
        assert result.auto_approve_allowed is False

    def test_auto_approve_blocked_non_returnable(self):
        ctx = self._default_ctx(1000.0, is_non_returnable=True)
        result = compute_price(ctx)
        assert result.auto_approve_allowed is False

    def test_tax_20_percent(self):
        ctx = self._default_ctx(1000.0, tax_rate=0.20, logistics_cost=0, target_margin_override=0.0)
        result = compute_price(ctx)
        # With zero margin and zero logistics, subtotal ≈ 1000, tax ≈ 200
        assert result.tax_amount == pytest.approx(result.subtotal_before_tax * 0.20, abs=1.0)
        
    def test_invalid_tax_rate_violation(self):
        ctx = self._default_ctx(1000.0, tax_rate=0.15)
        result = compute_price(ctx)
        assert any("Недопустимая ставка НДС" in v for v in result.violations)
        
    def test_high_margin_warning(self):
        ctx = self._default_ctx(1000.0, target_margin_override=0.60)
        result = compute_price(ctx)
        assert any("превышает 50%" in w for w in result.warnings)
