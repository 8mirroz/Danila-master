"""add_fleet_vehicles_and_tariffs

Revision ID: 50ece6030d5a
Revises: 1bc7f0a7982d
Create Date: 2026-07-08 06:30:00.677643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '50ece6030d5a'
down_revision: Union[str, Sequence[str], None] = '1bc7f0a7982d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # FleetVehicle table — 59 VINs from Contract Appendix 1
    op.create_table(
        'fleetvehicle',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False, default='default'),
        sa.Column('vin', sqlmodel.sql.sqltypes.AutoString(length=17), nullable=False, unique=True),
        sa.Column('make', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('engine', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('transmission', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('fuel_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('odometer_km', sa.Integer(), nullable=True, default=0),
        sa.Column('fuel_level_percent', sa.Integer(), nullable=True, default=100),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False, default='active'),  # active, maintenance, retired
        sa.Column('contract_ref', sqlmodel.sql.sqltypes.AutoString(), nullable=False, default='2026.170160'),
        sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fleetvehicle_tenant_id'), 'fleetvehicle', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_fleetvehicle_vin'), 'fleetvehicle', ['vin'], unique=True)
    op.create_index(op.f('ix_fleetvehicle_status'), 'fleetvehicle', ['status'], unique=False)

    # ServiceTariff table — Appendix 2 pricing
    op.create_table(
        'servicetariff',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False, default='default'),
        sa.Column('tariff_code', sqlmodel.sql.sqltypes.AutoString(), nullable=False, unique=True),
        sa.Column('service_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=False),  # diagnostics, maintenance, evacuation, on_site
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(), nullable=False, default='per_service'),  # per_service, per_km, per_hour
        sa.Column('base_price_rub', sa.Float(), nullable=False),
        sa.Column('vat_rate', sa.Float(), nullable=False, default=0.20),
        sa.Column('sla_hours', sa.Integer(), nullable=False),  # 2, 24, 168
        sa.Column('penalty_rate_per_day_pct', sa.Float(), nullable=False, default=0.1),  # 0.1% per day
        sa.Column('contract_ref', sqlmodel.sql.sqltypes.AutoString(), nullable=False, default='2026.170160'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_servicetariff_tenant_id'), 'servicetariff', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_servicetariff_tariff_code'), 'servicetariff', ['tariff_code'], unique=True)
    op.create_index(op.f('ix_servicetariff_category'), 'servicetariff', ['category'], unique=False)

    # ContractPenaltyConfig — single source of truth for penalty calculation
    op.create_table(
        'contractpenaltyconfig',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False, default='default'),
        sa.Column('contract_ref', sqlmodel.sql.sqltypes.AutoString(), nullable=False, unique=True),
        sa.Column('contract_total_value_rub', sa.Float(), nullable=False),  # 13,963,000 (example)
        sa.Column('penalty_pct_per_day', sa.Float(), nullable=False, default=0.001),  # 0.1%
        sa.Column('penalty_rub_per_day', sa.Float(), nullable=False),  # calculated: 13,963
        sa.Column('max_penalty_pct', sa.Float(), nullable=False, default=0.10),  # cap at 10%
        sa.Column('currency', sqlmodel.sql.sqltypes.AutoString(), nullable=False, default='RUB'),
        sa.Column('effective_from', sa.DateTime(), nullable=False),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contractpenaltyconfig_tenant_id'), 'contractpenaltyconfig', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_contractpenaltyconfig_contract_ref'), 'contractpenaltyconfig', ['contract_ref'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_contractpenaltyconfig_contract_ref'), table_name='contractpenaltyconfig')
    op.drop_index(op.f('ix_contractpenaltyconfig_tenant_id'), table_name='contractpenaltyconfig')
    op.drop_table('contractpenaltyconfig')

    op.drop_index(op.f('ix_servicetariff_category'), table_name='servicetariff')
    op.drop_index(op.f('ix_servicetariff_tariff_code'), table_name='servicetariff')
    op.drop_index(op.f('ix_servicetariff_tenant_id'), table_name='servicetariff')
    op.drop_table('servicetariff')

    op.drop_index(op.f('ix_fleetvehicle_status'), table_name='fleetvehicle')
    op.drop_index(op.f('ix_fleetvehicle_vin'), table_name='fleetvehicle')
    op.drop_index(op.f('ix_fleetvehicle_tenant_id'), table_name='fleetvehicle')
    op.drop_table('fleetvehicle')
