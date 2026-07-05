"""
Unit normalization and conversion logic.
"""
from typing import Dict, Optional

# Graph of unit conversions relative to a base unit for each quantity type
UNIT_GRAPH = {
    "length": {
        "base": "m",
        "conversions": {
            "m": 1.0,
            "см": 0.01,
            "мм": 0.001,
            "км": 1000.0
        }
    },
    "mass": {
        "base": "кг",
        "conversions": {
            "кг": 1.0,
            "г": 0.001,
            "т": 1000.0
        }
    },
    "volume": {
        "base": "л",
        "conversions": {
            "л": 1.0,
            "м³": 1000.0,
            "см³": 0.001
        }
    }
}

# specific product packing ratios
PRODUCT_PACK_RATIOS = {
    "Кабель UTP": {"коробка": 305.0}, # 1 коробка = 305m
}


def get_quantity_type(unit: str) -> Optional[str]:
    """Return the quantity type (length, mass, volume) for a given unit."""
    for q_type, data in UNIT_GRAPH.items():
        if unit in data["conversions"]:
            return q_type
    return None


def convert_units(
    q_src: float,
    p_src: float,
    u_src: str,
    u_target: str,
    product_name: str = ""
) -> Dict[str, float]:
    """
    Convert quantity and price from source unit to target unit.
    Returns {"q_target": float, "p_target": float}
    """
    if u_src == u_target:
        return {"q_target": q_src, "p_target": p_src}

    # Handle pack-specific conversions (like "коробка" to "м")
    k_src_base = 1.0
    k_target_base = 1.0
    
    q_type_src = get_quantity_type(u_src)
    q_type_target = get_quantity_type(u_target)

    # Resolve source unit coefficient
    if q_type_src:
        k_src_base = UNIT_GRAPH[q_type_src]["conversions"][u_src]
    elif u_src == "коробка":
        # Look up product specific pack ratio
        for p_key, packs in PRODUCT_PACK_RATIOS.items():
            if p_key.lower() in product_name.lower():
                k_src_base = packs.get("коробка", 1.0)
                q_type_src = get_quantity_type("м") # Assuming cables are measured in m
                break

    # Resolve target unit coefficient
    if q_type_target:
        k_target_base = UNIT_GRAPH[q_type_target]["conversions"][u_target]
    elif u_target == "коробка":
        for p_key, packs in PRODUCT_PACK_RATIOS.items():
            if p_key.lower() in product_name.lower():
                k_target_base = packs.get("коробка", 1.0)
                q_type_target = get_quantity_type("м")
                break
                
    # If the quantity types still don't match, we cannot convert
    if q_type_src != q_type_target and q_type_src is not None and q_type_target is not None:
        raise ValueError(f"Cannot convert between different quantity types: {u_src} and {u_target}")
    
    q_base = q_src * k_src_base
    q_target = q_base / k_target_base
    
    p_target = p_src * k_target_base / k_src_base
    
    return {
        "q_target": q_target,
        "p_target": p_target
    }
