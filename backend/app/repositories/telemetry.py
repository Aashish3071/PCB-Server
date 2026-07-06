from typing import Any, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.telemetry import Telemetry
from app.models.device import Device
from app.models.customer import Customer
from typing import Any
from app.repositories.base import BaseRepository
from app.schemas.device import DeviceAnalytics

class TelemetryRepository(BaseRepository[Telemetry, Any, Any]):
    
    async def get_device_telemetry_paginated(self, db: AsyncSession, device_id: UUID, skip: int = 0, limit: int = 20):
        stmt = select(Telemetry).where(Telemetry.device_id == device_id).order_by(desc(Telemetry.timestamp)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()
        
        count_stmt = select(func.count()).select_from(Telemetry).where(Telemetry.device_id == device_id)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0
        
        return items, total

    async def get_device_analytics(self, db: AsyncSession, device_id: UUID, since: datetime) -> DeviceAnalytics:
        # Aggregations
        agg_stmt = select(
            func.avg(Telemetry.battery_percentage),
            func.min(Telemetry.battery_percentage),
            func.max(Telemetry.battery_percentage),
            func.count(Telemetry.id)
        ).where(
            Telemetry.device_id == device_id,
            Telemetry.timestamp >= since
        )
        agg_result = await db.execute(agg_stmt)
        row = agg_result.first()
        
        battery_avg = row[0] if row and row[0] is not None else None
        battery_min = row[1] if row and row[1] is not None else None
        battery_max = row[2] if row and row[2] is not None else None
        daily_data_count = row[3] if row and row[3] is not None else 0

        # Latest Uptime
        latest_stmt = select(Telemetry.uptime_seconds).where(
            Telemetry.device_id == device_id
        ).order_by(desc(Telemetry.timestamp)).limit(1)
        latest_result = await db.execute(latest_stmt)
        uptime = latest_result.scalar_one_or_none()

        # Trend (last 24 hours). If it's too much data, we could sample, but let's just get it and limit to say 288 points (every 5 mins).
        trend_stmt = select(Telemetry.timestamp, Telemetry.battery_percentage).where(
            Telemetry.device_id == device_id,
            Telemetry.timestamp >= since,
            Telemetry.battery_percentage.is_not(None)
        ).order_by(Telemetry.timestamp).limit(300)
        
        trend_result = await db.execute(trend_stmt)
        trend_rows = trend_result.all()
        
        battery_trend = []
        for t_row in trend_rows:
            battery_trend.append({
                "timestamp": t_row[0].isoformat(),
                "battery_percentage": t_row[1]
            })

        return DeviceAnalytics(
            battery_avg=battery_avg,
            battery_min=battery_min,
            battery_max=battery_max,
            uptime_seconds=uptime,
            daily_data_count=daily_data_count,
            battery_trend=battery_trend
        )

    async def search_fleet_telemetry(
        self,
        db: AsyncSession,
        device_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 20
    ):
        query = select(Telemetry, Device.device_name, Device.device_uid, Customer.company_name).select_from(Telemetry)\
            .join(Device, Telemetry.device_id == Device.id)\
            .outerjoin(Customer, Device.customer_id == Customer.id)
            
        count_query = select(func.count()).select_from(Telemetry)\
            .join(Device, Telemetry.device_id == Device.id)\
            .outerjoin(Customer, Device.customer_id == Customer.id)
            
        if device_id:
            query = query.filter(Telemetry.device_id == device_id)
            count_query = count_query.filter(Telemetry.device_id == device_id)
            
        if customer_id:
            query = query.filter(Device.customer_id == customer_id)
            count_query = count_query.filter(Device.customer_id == customer_id)
            
        if start_date:
            query = query.filter(Telemetry.timestamp >= start_date)
            count_query = count_query.filter(Telemetry.timestamp >= start_date)
            
        if end_date:
            query = query.filter(Telemetry.timestamp <= end_date)
            count_query = count_query.filter(Telemetry.timestamp <= end_date)
            
        query = query.order_by(desc(Telemetry.timestamp)).offset(skip).limit(limit)
        
        results = await db.execute(query)
        total = await db.execute(count_query)
        
        return results.all(), total.scalar_one()

telemetry_repo = TelemetryRepository(Telemetry)
