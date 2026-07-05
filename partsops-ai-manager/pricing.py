"""
PartsOps AI Manager v3 — Pricing & Margin Guard
Implements pricing formula, margin policy, and price anomaly detection.
"""
from dataclasses import dataclass, field
from typing import Optional, List
import math
import statistics


# ──────────────────────────────────────────────
# Margin Policy (from v3 system contract)
# ──────────────────────────────────────────────

MARGIN_POLICY = {
    "default": 0.12,
    "original_bmw": 0.10,
    "non_returnable": 0.18,
    "high_risk_supplier": 0.20,
    "aftermarket_safety_critical": 0.22,
}

PRICE_ANOMALY_THRESHOLD = 0.20  # 20% deviation from 90-day median triggers review
AUTO_APPROVE_MATCH_SCORE_MIN = 0.88
AUTO_APPROVE_SUPPLIER_RELIABILITY_MIN = 0.75
AUTO_APPROVE_PRICE_DEVIATION_MAX = 0.15


# ──────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────

@dataclass
class PricingContext:
    purchase_price: float
    currency: str = "RUB"
    logistics_cost: float = 0.0
    urgency_level: str = "normal"            # low|normal|urgent|critical
    supplier_reliability_score: float = 1.0
    is_non_returnable: bool = False
    is_safety_critical: bool = False
    is_original: bool = False
    brand_group: str = "default"             # default|original_bmw|aftermarket
    target_margin_override: Optional[float] = None
    tax_rate: float = 0.20                   # 20% VAT Russia default
    historical_median_price_90d: Optional[float] = None
    historical_prices_90d: Optional[List[float]] = None



@dataclass
class PricingResult:
    purchase_price: float
    logistics_cost: float
    risk_buffer: float
    urgency_buffer: float
    margin_amount: float
    margin_rate: float
    subtotal_before_tax: float
    tax_amount: float
    client_price: float
    currency: str
    policy_min_margin: float
    margin_policy_passed: bool
    price_anomaly_detected: bool
    price_deviation: Optional[float]
    auto_approve_allowed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# Pricing formula
# ──────────────────────────────────────────────

URGENCY_BUFFER_RATES = {
    "low": 0.0,
    "normal": 0.0,
    "urgent": 0.05,    # +5% for urgent
    "critical": 0.10,  # +10% for critical
}


def compute_price(ctx: PricingContext) -> PricingResult:
    """
    v3 Pricing formula:
    client_price =
        purchase_price
        + logistics_cost
        + supplier_risk_buffer    (based on reliability)
        + urgency_buffer          (based on urgency level)
        + target_margin           (based on policy)
        + tax_adjustment
    """
    violations = []
    warnings = []

    # 1. Determine policy minimum margin
    if ctx.is_non_returnable:
        policy_min_margin = MARGIN_POLICY["non_returnable"]
    elif ctx.is_safety_critical and ctx.brand_group != "original_bmw":
        policy_min_margin = MARGIN_POLICY["aftermarket_safety_critical"]
    elif ctx.brand_group == "original_bmw":
        policy_min_margin = MARGIN_POLICY["original_bmw"]
    elif ctx.supplier_reliability_score < 0.75:
        policy_min_margin = MARGIN_POLICY["high_risk_supplier"]
    else:
        policy_min_margin = MARGIN_POLICY["default"]

    # 2. Supplier risk buffer (inverse of reliability)
    reliability_gap = max(0.0, 0.85 - ctx.supplier_reliability_score)
    risk_buffer = ctx.purchase_price * reliability_gap * 0.15

    # 3. Urgency buffer
    urgency_rate = URGENCY_BUFFER_RATES.get(ctx.urgency_level, 0.0)
    urgency_buffer = ctx.purchase_price * urgency_rate

    # 4. Target margin
    target_margin_rate = ctx.target_margin_override or policy_min_margin
    base = ctx.purchase_price + ctx.logistics_cost + risk_buffer + urgency_buffer
    margin_amount = base * target_margin_rate

    # 5. Pre-tax total
    subtotal = base + margin_amount

    # 6. Tax (VAT)
    tax_amount = round(subtotal * ctx.tax_rate, 2)
    client_price = round(subtotal + tax_amount, 2)

    actual_margin_rate = margin_amount / (ctx.purchase_price + ctx.logistics_cost) if (ctx.purchase_price + ctx.logistics_cost) > 0 else 0
    margin_policy_passed = actual_margin_rate >= policy_min_margin

    if not margin_policy_passed:
        violations.append(
            f"Маржинальность {actual_margin_rate:.1%} ниже минимума политики {policy_min_margin:.1%}"
        )
    
    if actual_margin_rate > 0.50:
        warnings.append(
            f"Маржинальность {actual_margin_rate:.1%} превышает 50%, требуется ручное одобрение"
        )
        
    if ctx.tax_rate not in (0.0, 0.20):
        violations.append(
            f"Недопустимая ставка НДС: {ctx.tax_rate}. Разрешено только 0.0 или 0.20."
        )

    # 7. Price anomaly check (Z-score, IQR, Delta)
    price_anomaly_detected = False
    price_deviation = None
    
    if ctx.historical_prices_90d and len(ctx.historical_prices_90d) > 3:
        history = ctx.historical_prices_90d
        # Delta
        last_price = history[-1]
        price_deviation = abs(ctx.purchase_price - last_price) / last_price if last_price > 0 else 0
        
        # Z-score
        mean_p = statistics.mean(history)
        stdev_p = statistics.stdev(history) if len(history) > 1 else 1.0
        z_score = abs(ctx.purchase_price - mean_p) / stdev_p if stdev_p > 0 else 0
        
        # IQR
        sorted_h = sorted(history)
        q1 = sorted_h[len(sorted_h)//4]
        q3 = sorted_h[(len(sorted_h)*3)//4]
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        is_iqr_anomaly = ctx.purchase_price < lower_bound or ctx.purchase_price > upper_bound
        is_delta_anomaly = price_deviation > PRICE_ANOMALY_THRESHOLD
        is_z_anomaly = z_score > 2.5
        
        price_anomaly_detected = is_iqr_anomaly or is_delta_anomaly or is_z_anomaly
        
        if price_anomaly_detected:
            warnings.append(
                f"Обнаружена аномалия цены! Z-оценка: {z_score:.2f}, "
                f"Отклонение: {price_deviation:.1%}, границы IQR: [{lower_bound:.0f}, {upper_bound:.0f}]"
            )
    elif ctx.historical_median_price_90d and ctx.historical_median_price_90d > 0:
        price_deviation = abs(ctx.purchase_price - ctx.historical_median_price_90d) / ctx.historical_median_price_90d
        price_anomaly_detected = price_deviation > PRICE_ANOMALY_THRESHOLD
        if price_anomaly_detected:
            warnings.append(
                f"Аномалия цены: текущая {ctx.purchase_price:.0f} vs 90дн. медиана {ctx.historical_median_price_90d:.0f} "
                f"(отклонение {price_deviation:.1%})"
            )

    # 8. Auto-approve eligibility
    auto_approve_allowed = (
        margin_policy_passed
        and not price_anomaly_detected
        and ctx.supplier_reliability_score >= AUTO_APPROVE_SUPPLIER_RELIABILITY_MIN
        and not ctx.is_non_returnable
        and not ctx.is_safety_critical
    )

    return PricingResult(
        purchase_price=ctx.purchase_price,
        logistics_cost=ctx.logistics_cost,
        risk_buffer=round(risk_buffer, 2),
        urgency_buffer=round(urgency_buffer, 2),
        margin_amount=round(margin_amount, 2),
        margin_rate=round(actual_margin_rate, 4),
        subtotal_before_tax=round(subtotal, 2),
        tax_amount=tax_amount,
        client_price=client_price,
        currency=ctx.currency,
        policy_min_margin=policy_min_margin,
        margin_policy_passed=margin_policy_passed,
        price_anomaly_detected=price_anomaly_detected,
        price_deviation=round(price_deviation, 4) if price_deviation is not None else None,
        auto_approve_allowed=auto_approve_allowed,
        violations=violations,
        warnings=warnings,
    )


def check_margin_guard(
    purchase_price: float,
    sale_price: float,
    policy_key: str = "default",
) -> dict:
    """
    Simple margin guard for cases where pricing is done externally.
    Returns {"passed": bool, "margin": float, "min_margin": float, "violation": str|None}
    """
    if purchase_price <= 0:
        return {"passed": False, "margin": 0.0, "min_margin": 0.0, "violation": "закупочная цена должна быть > 0"}

    margin = (sale_price - purchase_price) / purchase_price
    min_margin = MARGIN_POLICY.get(policy_key, MARGIN_POLICY["default"])
    passed = margin >= min_margin
    return {
        "passed": passed,
        "margin": round(margin, 4),
        "min_margin": min_margin,
        "violation": None if passed else f"Маржинальность {margin:.1%} < минимума политики {min_margin:.1%}",
    }

# ──────────────────────────────────────────────
# Invoicing and Forecasting Algorithms
# ──────────────────────────────────────────────

def calculate_invoice(
    items: List[dict],
    tax_rate: float = 0.20,
    base_delivery: float = 0.0,
    delivery_rate_per_kg: float = 0.0,
    distance_km: float = 0.0
) -> dict:
    """
    Calculate complete invoice totals based on items list, volume discounts and delivery rules.
    items = [{"price": float, "qty": int, "weight_kg": float}]
    """
    subtotal = sum(item["price"] * item["qty"] for item in items)
    
    # Volume discount
    discount = 0.0
    if subtotal >= 500000:
        discount = 0.07
    elif subtotal >= 200000:
        discount = 0.05
    elif subtotal >= 50000:
        discount = 0.03
        
    after_discount = subtotal * (1 - discount)
    vat = after_discount * tax_rate
    
    total_weight = sum(item.get("weight_kg", 0) * item["qty"] for item in items)
    delivery = base_delivery + (delivery_rate_per_kg * total_weight * distance_km)
    
    total = after_discount + vat + delivery
    
    return {
        "subtotal": subtotal,
        "discount_rate": discount,
        "discount_amount": subtotal * discount,
        "after_discount": after_discount,
        "vat": vat,
        "delivery": delivery,
        "total": total
    }

def holt_winters_forecast(
    prices: List[float], 
    alpha: float = 0.3, 
    beta: float = 0.1, 
    horizon: int = 7
) -> List[float]:
    """
    Predict future prices using Holt-Winters exponential smoothing (Trend only).
    """
    if not prices:
        return []
        
    if len(prices) == 1:
        return [prices[0]] * horizon
        
    L = [prices[0]]
    T = [prices[1] - prices[0]]
    
    for i in range(1, len(prices)):
        L_t = alpha * prices[i] + (1 - alpha) * (L[i-1] + T[i-1])
        T_t = beta * (L_t - L[i-1]) + (1 - beta) * T[i-1]
        
        L.append(L_t)
        T.append(T_t)
        
    last_L = L[-1]
    last_T = T[-1]
    
    forecasts = []
    for h in range(1, horizon + 1):
        forecasts.append(last_L + h * last_T)
        
    return forecasts

