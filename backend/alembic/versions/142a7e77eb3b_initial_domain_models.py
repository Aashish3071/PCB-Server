"""Initial domain models

Revision ID: 142a7e77eb3b
Revises: 
Create Date: 2026-07-06 00:11:34

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '142a7e77eb3b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users Table
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Customers Table
    op.create_table(
        'customers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_name', sa.String(), nullable=False),
        sa.Column('contact_person', sa.String(), nullable=True),
        sa.Column('contact_email', sa.String(), nullable=True),
        sa.Column('contact_phone', sa.String(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_company_name'), 'customers', ['company_name'], unique=False)

    # Devices Table
    op.create_table(
        'devices',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('device_uid', sa.String(), nullable=False),
        sa.Column('customer_id', sa.UUID(), nullable=False),
        sa.Column('device_name', sa.String(), nullable=False),
        sa.Column('device_type', sa.String(), nullable=False, server_default='solar_rms'),
        sa.Column('api_key_hash', sa.String(), nullable=False),
        sa.Column('firmware_version', sa.String(), nullable=True),
        sa.Column('installation_location', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='OFFLINE'),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'device_name', name='uq_customer_device_name')
    )
    op.create_index(op.f('ix_devices_customer_id'), 'devices', ['customer_id'], unique=False)
    op.create_index(op.f('ix_devices_device_uid'), 'devices', ['device_uid'], unique=True)
    op.create_index(op.f('ix_devices_last_seen_at'), 'devices', ['last_seen_at'], unique=False)

    # Telemetry Table
    op.create_table(
        'telemetry',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('device_id', sa.UUID(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('humidity', sa.Float(), nullable=True),
        sa.Column('panel_voltage', sa.Float(), nullable=True),
        sa.Column('charging_current', sa.Float(), nullable=True),
        sa.Column('battery_voltage', sa.Float(), nullable=True),
        sa.Column('battery_percentage', sa.Float(), nullable=True),
        sa.Column('charging_status', sa.Boolean(), nullable=True),
        sa.Column('light_load_status', sa.Boolean(), nullable=True),
        sa.Column('signal_strength', sa.Integer(), nullable=True),
        sa.Column('server_received_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_id', 'timestamp', name='uq_device_timestamp')
    )
    op.create_index(op.f('ix_telemetry_server_received_at'), 'telemetry', ['server_received_at'], unique=False)
    op.create_index('ix_telemetry_device_id_timestamp_desc', 'telemetry', ['device_id', sa.text('timestamp DESC')], unique=False)

    # Alerts Table
    op.create_table(
        'alerts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('device_id', sa.UUID(), nullable=False),
        sa.Column('alert_type', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_device_id'), 'alerts', ['device_id'], unique=False)
    op.create_index(op.f('ix_alerts_is_resolved'), 'alerts', ['is_resolved'], unique=False)


def downgrade() -> None:
    op.drop_table('alerts')
    op.drop_table('telemetry')
    op.drop_table('devices')
    op.drop_table('customers')
    op.drop_table('users')
