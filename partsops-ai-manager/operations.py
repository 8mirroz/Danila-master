"""
Operations algorithms: Greedy Minimum Weight Set Cover and Multi-Criteria Ranking (SAW).
"""
from typing import List, Dict, Set, Any
import math

# ──────────────────────────────────────────────
# Ranking (SAW)
# ──────────────────────────────────────────────

def normalize(value: float, v_min: float, v_max: float, larger_is_better: bool = True) -> float:
    """Normalize value to [0, 1] range using min-max normalization."""
    if v_max == v_min:
        return 1.0 if larger_is_better else 0.0
    if larger_is_better:
        return (value - v_min) / (v_max - v_min)
    else:
        return (v_max - value) / (v_max - v_min)

def rank_offers(offers: List[Dict[str, Any]], weights: Dict[str, float] = None) -> List[Dict[str, Any]]:
    """
    Rank offers using Simple Additive Weighting (SAW).
    Expected offer format:
    {
        "supplier_name": str,
        "price": float,
        "stock": int,
        "delivery_days": int,
        "reliability": float,
        "history": float
    }
    """
    if not offers:
        return []

    if weights is None:
        weights = {
            "price": 0.40,
            "stock": 0.25,
            "delivery_days": 0.15,
            "reliability": 0.12,
            "history": 0.08
        }
    
    # Extract min/max for normalization
    stats = {
        "price": {"min": min(o["price"] for o in offers), "max": max(o["price"] for o in offers)},
        "stock": {"min": min(o["stock"] for o in offers), "max": max(o["stock"] for o in offers)},
        "delivery_days": {"min": min(o["delivery_days"] for o in offers), "max": max(o["delivery_days"] for o in offers)},
        "reliability": {"min": min(o["reliability"] for o in offers), "max": max(o["reliability"] for o in offers)},
        "history": {"min": min(o.get("history", 0) for o in offers), "max": max(o.get("history", 0) for o in offers)},
    }
    
    for offer in offers:
        r_price = normalize(offer["price"], stats["price"]["min"], stats["price"]["max"], larger_is_better=False)
        r_stock = normalize(offer["stock"], stats["stock"]["min"], stats["stock"]["max"], larger_is_better=True)
        r_days = normalize(offer["delivery_days"], stats["delivery_days"]["min"], stats["delivery_days"]["max"], larger_is_better=False)
        r_rel = normalize(offer["reliability"], stats["reliability"]["min"], stats["reliability"]["max"], larger_is_better=True)
        r_hist = normalize(offer.get("history", 0), stats["history"]["min"], stats["history"]["max"], larger_is_better=True)
        
        offer["rank_score"] = (
            weights["price"] * r_price +
            weights["stock"] * r_stock +
            weights["delivery_days"] * r_days +
            weights["reliability"] * r_rel +
            weights["history"] * r_hist
        )
    
    return sorted(offers, key=lambda x: x["rank_score"], reverse=True)


# ──────────────────────────────────────────────
# Greedy Minimum Weight Set Cover
# ──────────────────────────────────────────────

def calculate_optimal_coverage(
    requested_items: List[Dict[str, Any]], 
    suppliers: List[Dict[str, Any]],
    alpha: float = 0.7,
    beta: float = 0.2,
    gamma: float = 0.1
) -> Dict[str, Any]:
    """
    Greedy Set Cover approximation for fulfilling an order across multiple suppliers.
    requested_items: list of {"name": str, "qty": int, "id": int|str}
    suppliers: list of {"name": str, "items": dict(item_id -> price), "rating": float}
    """
    uncovered = set(item["id"] for item in requested_items)
    assignment = {}
    used_suppliers = set()
    total_cost = 0.0

    while uncovered:
        best_sup = None
        best_score = float("inf")
        best_covered = []
        best_cost = 0.0
        
        for sup in suppliers:
            cost = 0.0
            covered_items = []
            
            for item in requested_items:
                if item["id"] in uncovered and item["id"] in sup["items"]:
                    price = sup["items"][item["id"]]
                    cost += price * item["qty"]
                    covered_items.append({"item_id": item["id"], "price": price, "qty": item["qty"]})
            
            if not covered_items:
                continue
            
            # Score: cost per covered item - bonus for consolidation + penalty for low rating
            covered_count = len(covered_items)
            consolidation_bonus = -500 if sup["name"] in used_suppliers else 0
            penalty = (1.0 - sup.get("rating", 1.0)) * 1000
            
            score = alpha * (cost / covered_count) - beta * (covered_count * 100) + consolidation_bonus + gamma * penalty
            
            if score < best_score:
                best_score = score
                best_sup = sup
                best_covered = covered_items
                best_cost = cost
        
        if not best_sup:
            break
            
        used_suppliers.add(best_sup["name"])
        assignment[best_sup["name"]] = assignment.get(best_sup["name"], []) + best_covered
        total_cost += best_cost
        
        for cov in best_covered:
            uncovered.remove(cov["item_id"])

    return {
        "assignments": assignment,
        "uncovered_item_ids": list(uncovered),
        "total_cost": total_cost,
        "supplier_count": len(used_suppliers)
    }
