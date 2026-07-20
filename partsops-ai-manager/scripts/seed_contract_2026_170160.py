"""
Seeder: Contract № 2026.170160 reference data.

- 59 fleet vehicles (Appendix 1)
- Service tariffs (Appendix 2)
- Penalty configuration
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from sqlmodel import Session, select

from models import FleetVehicle, ServiceTariff, ContractPenaltyConfig


# ──────────────────────────────────────────────────────────────
# APPENDIX 1 — 59 VINs
# Mix of VW Crafter and ГАЗ variants (VIN prefixes match real patterns).
# Full 59-item registry; replace placeholders with actual Appendix 1 data.
# ──────────────────────────────────────────────────────────────

FLEET_VEHICLES: List[dict] = [
    # VW Crafter (1st gen) — VIN starts with WV1ZZZ
    {"vin": "WV1ZZZ12Z5H000001", "make": "Volkswagen", "model": "Crafter 30", "year": 2008},
    {"vin": "WV1ZZZ12Z5H000002", "make": "Volkswagen", "model": "Crafter 35", "year": 2009},
    {"vin": "WV1ZZZ12Z5H000003", "make": "Volkswagen", "model": "Crafter 50", "year": 2010},
    {"vin": "WV1ZZZ12Z5H000004", "make": "Volkswagen", "model": "Crafter 30", "year": 2011},
    {"vin": "WV1ZZZ12Z5H000005", "make": "Volkswagen", "model": "Crafter 35", "year": 2012},
    {"vin": "WV1ZZZ12Z5H000006", "make": "Volkswagen", "model": "Crafter 50", "year": 2013},
    {"vin": "WV1ZZZ12Z5H000007", "make": "Volkswagen", "model": "Crafter 30", "year": 2013},
    {"vin": "WV1ZZZ12Z5H000008", "make": "Volkswagen", "model": "Crafter 35", "year": 2014},
    {"vin": "WV1ZZZ12Z5H000009", "make": "Volkswagen", "model": "Crafter 50", "year": 2015},
    {"vin": "WV1ZZZ12Z5H000010", "make": "Volkswagen", "model": "Crafter 30", "year": 2015},
    {"vin": "WV1ZZZ12Z5H000011", "make": "Volkswagen", "model": "Crafter 35", "year": 2016},
    {"vin": "WV1ZZZ12Z5H000012", "make": "Volkswagen", "model": "Crafter 50", "year": 2017},
    {"vin": "WV1ZZZ12Z5H000013", "make": "Volkswagen", "model": "Crafter 30", "year": 2017},
    {"vin": "WV1ZZZ12Z5H000014", "make": "Volkswagen", "model": "Crafter 35", "year": 2018},
    {"vin": "WV1ZZZ12Z5H000015", "make": "Volkswagen", "model": "Crafter 50", "year": 2019},
    # VW Crafter (2nd gen / MAN-based) — VIN starts with WV1ZZZ2
    {"vin": "WV1ZZZ2C7KH000016", "make": "Volkswagen", "model": "Crafter 30", "year": 2019},
    {"vin": "WV1ZZZ2C7KJ000017", "make": "Volkswagen", "model": "Crafter 35", "year": 2020},
    {"vin": "WV1ZZZ2C7KL000018", "make": "Volkswagen", "model": "Crafter 50", "year": 2020},
    {"vin": "WV1ZZZ2C7KH000019", "make": "Volkswagen", "model": "Crafter 30", "year": 2021},
    {"vin": "WV1ZZZ2C7KJ000020", "make": "Volkswagen", "model": "Crafter 35", "year": 2021},
    {"vin": "WV1ZZZ2C7KL000021", "make": "Volkswagen", "model": "Crafter 50", "year": 2022},
    {"vin": "WV1ZZZ2C7KH000022", "make": "Volkswagen", "model": "Crafter 30", "year": 2022},
    {"vin": "WV1ZZZ2C7KJ000023", "make": "Volkswagen", "model": "Crafter 35", "year": 2023},
    {"vin": "WV1ZZZ2C7KL000024", "make": "Volkswagen", "model": "Crafter 50", "year": 2023},
    {"vin": "WV1ZZZ2C7KH000025", "make": "Volkswagen", "model": "Crafter 30", "year": 2024},
    # ГАЗель Next / ГАЗель Long / ГАЗель Business — VIN starts with XTH
    {"vin": "XTH814000K000026", "make": "ГАЗ", "model": "ГАЗель Next", "year": 2018},
    {"vin": "XTH814000K000027", "make": "ГАЗ", "model": "ГАЗель Next", "year": 2019},
    {"vin": "XTH814000K000028", "make": "ГАЗ", "model": "ГАЗель Next", "year": 2020},
    {"vin": "XTH814000K000029", "make": "ГАЗ", "model": "ГАЗель Next", "year": 2020},
    {"vin": "XTH814000K000030", "make": "ГАЗ", "model": "ГАЗель Long", "year": 2021},
    {"vin": "XTH814000K000031", "make": "ГАЗ", "model": "ГАЗель Next", "year": 2021},
    {"vin": "XTH814000K000032", "make": "ГАЗ", "model": "ГАЗель Business", "year": 2022},
    {"vin": "XTH814000K000033", "make": "ГАЗ", "model": "ГАЗель Next", "year": 2022},
    {"vin": "XTH814000K000034", "make": "ГАЗ", "model": "ГАЗель Long", "year": 2023},
    {"vin": "XTH814000K000035", "make": "ГАЗ", "model": "ГАЗель Next", "year": 2023},
    {"vin": "XTH814000K000036", "make": "ГАЗ", "model": "ГАЗель Business", "year": 2024},
    {"vin": "XTH814000K000037", "make": "ГАЗ", "model": "ГАЗель Next", "year": 2024},
    # ГАЗель Универсал / ГАЗ-3309
    {"vin": "XTH330900K000038", "make": "ГАЗ", "model": "ГАЗ-3309", "year": 2017},
    {"vin": "XTH330900K000039", "make": "ГАЗ", "model": "ГАЗ-3309", "year": 2018},
    {"vin": "XTH330900K000040", "make": "ГАЗ", "model": "ГАЗ-3309", "year": 2019},
    {"vin": "XTH330900K000041", "make": "ГАЗ", "model": "ГАЗ-3309", "year": 2020},
    {"vin": "XTH330900K000042", "make": "ГАЗ", "model": "ГАЗ-3309", "year": 2021},
    # ГАЗон Next / ГАЗon City — VIN starts with XTH...
    {"vin": "XTHC1N000K000043", "make": "ГАЗ", "model": "ГАЗон Next", "year": 2021},
    {"vin": "XTHC1N000K000044", "make": "ГАЗ", "model": "ГАЗон Next", "year": 2022},
    {"vin": "XTHC1N000K000045", "make": "ГАЗ", "model": "ГАЗон Next", "year": 2023},
    {"vin": "XTHC1N000K000046", "make": "ГАЗ", "model": "ГАЗon City", "year": 2023},
    {"vin": "XTHC1N000K000047", "make": "ГАЗ", "model": "ГАЗon Next", "year": 2024},
    {"vin": "XTHC1N000K000048", "make": "ГАЗ", "model": "ГАЗon City", "year": 2024},
    # Additional fleet vehicles (common Russian commercial + VW Crafter rounds)
    {"vin": "WV1ZZZ2C7KH000049", "make": "Volkswagen", "model": "Crafter 35", "year": 2024},
    {"vin": "WV1ZZZ2C7KL000050", "make": "Volkswagen", "model": "Crafter 50", "year": 2024},
    {"vin": "XTH814000K000051", "make": "ГАЗ", "model": "ГАЗель Next", "year": 2025},
    {"vin": "XTH814000K000052", "make": "ГАЗ", "model": "ГАЗель Long", "year": 2025},
    {"vin": "XTH814000K000053", "make": "ГАЗ", "model": "ГАЗель Business", "year": 2025},
    {"vin": "XTHC1N000K000054", "make": "ГАЗ", "model": "ГАЗон Next", "year": 2025},
    {"vin": "XTHC1N000K000055", "make": "ГАЗ", "model": "ГАЗon City", "year": 2025},
    {"vin": "WV1ZZZ12Z5H000056", "make": "Volkswagen", "model": "Crafter 35", "year": 2016},
    {"vin": "WV1ZZZ12Z5H000057", "make": "Volkswagen", "model": "Crafter 50", "year": 2011},
    {"vin": "XTH330900K000058", "make": "ГАЗ", "model": "ГАЗ-3309", "year": 2022},
    {"vin": "XTH330900K000059", "make": "ГАЗ", "model": "ГАЗ-3309", "year": 2023},
]


# ──────────────────────────────────────────────────────────────
# APPENDIX 2 — Service tariffs
# All positions from Appendix 2 are 2425.50 RUB, except:
#   эвакуатор 6600 RUB, выезд 4950 RUB
# SLA: диагностика 2 часа, ТО 24 часа.
# ──────────────────────────────────────────────────────────────

SERVICE_TARIFFS: List[dict] = [
    {
        "tariff_code": "DIAG-FACTORY-001",
        "service_name": "Компьютерная диагностика (дилер)",
        "category": "diagnostics",
        "unit": "per_service",
        "base_price_rub": 2425.50,
        "vat_rate": 0.20,
        "sla_hours": 2,
        "penalty_rate_per_day_pct": 0.001,
    },
    {
        "tariff_code": "DIAG-BASIC-001",
        "service_name": "Компьютерная диагностика (базовая)",
        "category": "diagnostics",
        "unit": "per_service",
        "base_price_rub": 2425.50,
        "vat_rate": 0.20,
        "sla_hours": 2,
        "penalty_rate_per_day_pct": 0.001,
    },
    {
        "tariff_code": "DIAG-ELECTRIC-001",
        "service_name": "Диагностика электрооборудования",
        "category": "diagnostics",
        "unit": "per_service",
        "base_price_rub": 2425.50,
        "vat_rate": 0.20,
        "sla_hours": 2,
        "penalty_rate_per_day_pct": 0.001,
    },
    {
        "tariff_code": "DIAG-ABS-001",
        "service_name": "Диагностика ABS / ESP",
        "category": "diagnostics",
        "unit": "per_service",
        "base_price_rub": 2425.50,
        "vat_rate": 0.20,
        "sla_hours": 2,
        "penalty_rate_per_day_pct": 0.001,
    },
    {
        "tariff_code": "TO-PERIODIC-001",
        "service_name": "Плановое ТО (среднее)",
        "category": "maintenance",
        "unit": "per_service",
        "base_price_rub": 2425.50,
        "vat_rate": 0.20,
        "sla_hours": 24,
        "penalty_rate_per_day_pct": 0.001,
    },
    {
        "tariff_code": "EVACUATION-001",
        "service_name": "Эвакуация",
        "category": "evacuation",
        "unit": "per_service",
        "base_price_rub": 6600.00,
        "vat_rate": 0.20,
        "sla_hours": 24,
        "penalty_rate_per_day_pct": 0.001,
    },
    {
        "tariff_code": "ON-SITE-VISIT-001",
        "service_name": "Выезд мастера",
        "category": "on_site",
        "unit": "per_service",
        "base_price_rub": 4950.00,
        "vat_rate": 0.20,
        "sla_hours": 24,
        "penalty_rate_per_day_pct": 0.001,
    },
]


# ──────────────────────────────────────────────────────────────
# PENALTY CONFIG — Contract № 2026.170160
# penalty 0.1%/day => 13 963 RUB/day if contract value = 13 963 000
# ──────────────────────────────────────────────────────────────

PENALTY_CONFIG: dict = {
    "contract_ref": "2026.170160",
    "contract_total_value_rub": 13_963_000.0,
    "penalty_pct_per_day": 0.001,
    "penalty_rub_per_day": round(13_963_000.0 * 0.001, 2),
    "max_penalty_pct": 0.10,
    "currency": "RUB",
    "effective_from": datetime(2026, 1, 1),
}


def seed_fleet_and_tariffs(session: Session, *, dry_run: bool = True) -> dict:
    """Insert or update fleet vehicles, tariffs, and penalty config for the tenant."""
    tenant_id = "default"
    added_fleet = 0
    added_tariffs = 0
    updated_tariffs = 0
    penalty_upserted = False

    # Fleet vehicles
    for row in FLEET_VEHICLES:
        existing = session.exec(
            select(FleetVehicle).where(
                FleetVehicle.tenant_id == tenant_id,
                FleetVehicle.vin == row["vin"],
            )
        ).first()

        defaults = {
            "make": row["make"],
            "model": row["model"],
            "year": row["year"],
            "contract_ref": "2026.170160",
            "status": "active",
            "updated_at": datetime.utcnow(),
        }

        if not existing:
            session.add(FleetVehicle(
                tenant_id=tenant_id,
                vin=row["vin"],
                **defaults,
                created_at=datetime.utcnow(),
            ))
            added_fleet += 1
        else:
            needs_update = False
            for key, val in defaults.items():
                if getattr(existing, key) != val:
                    setattr(existing, key, val)
                    needs_update = True
            if needs_update:
                session.add(existing)

    # Service tariffs (upsert by tariff_code)
    for row in SERVICE_TARIFFS:
        existing = session.exec(
            select(ServiceTariff).where(
                ServiceTariff.tenant_id == tenant_id,
                ServiceTariff.tariff_code == row["tariff_code"],
            )
        ).first()

        if not existing:
            session.add(ServiceTariff(
                tenant_id=tenant_id,
                tariff_code=row["tariff_code"],
                service_name=row["service_name"],
                category=row["category"],
                unit=row["unit"],
                base_price_rub=row["base_price_rub"],
                vat_rate=row["vat_rate"],
                sla_hours=row["sla_hours"],
                penalty_rate_per_day_pct=row["penalty_rate_per_day_pct"],
                contract_ref="2026.170160",
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ))
            added_tariffs += 1
        else:
            # Update mutable fields
            existing.base_price_rub = row["base_price_rub"]
            existing.sla_hours = row["sla_hours"]
            existing.penalty_rate_per_day_pct = row["penalty_rate_per_day_pct"]
            existing.updated_at = datetime.utcnow()
            session.add(existing)
            updated_tariffs += 1

    # Penalty config (single row, upsert by contract_ref)
    existing_config = session.exec(
        select(ContractPenaltyConfig).where(
            ContractPenaltyConfig.tenant_id == tenant_id,
            ContractPenaltyConfig.contract_ref == PENALTY_CONFIG["contract_ref"],
        )
    ).first()

    if not existing_config:
        session.add(ContractPenaltyConfig(
            tenant_id=tenant_id,
            **PENALTY_CONFIG,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ))
        penalty_upserted = True
    else:
        existing_config.contract_total_value_rub = PENALTY_CONFIG["contract_total_value_rub"]
        existing_config.penalty_pct_per_day = PENALTY_CONFIG["penalty_pct_per_day"]
        existing_config.penalty_rub_per_day = PENALTY_CONFIG["penalty_rub_per_day"]
        existing_config.max_penalty_pct = PENALTY_CONFIG["max_penalty_pct"]
        existing_config.currency = PENALTY_CONFIG["currency"]
        existing_config.updated_at = datetime.utcnow()
        session.add(existing_config)
        penalty_upserted = True

    if not dry_run:
        session.commit()

    return {
        "tenant_id": tenant_id,
        "fleet_vehicles": len(FLEET_VEHICLES),
        "added_fleet": added_fleet,
        "service_tariffs": len(SERVICE_TARIFFS),
        "added_tariffs": added_tariffs,
        "updated_tariffs": updated_tariffs,
        "penalty_config_upserted": penalty_upserted,
        "contract_ref": "2026.170160",
        "dry_run": dry_run,
    }


if __name__ == "__main__":
    from database import get_session
    with next(get_session()) as session:
        result = seed_fleet_and_tariffs(session)
        print(result)
