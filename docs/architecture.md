# Architecture

This document tracks the core architectural decisions for the IoT DMS platform.

## 1. Core Principles

- **FastAPI is the Application**: All business logic (telemetry, alerts, customer/device management) lives inside the FastAPI backend.
- **Supabase is Infrastructure**: Supabase provides the PostgreSQL database and Admin Authentication. The application must remain portable to any standard PostgreSQL database. Business logic must not depend on Supabase-specific features.
- **Strict Data Flow**: React never accesses the database directly. It communicates exclusively with the FastAPI backend (with the sole exception of the Supabase Auth module for logging in).

## 2. Authentication Strategy

- **Administrator Authentication**: Uses Supabase Auth (Email + Password). The frontend uses the Supabase JS client to authenticate and obtain a JWT. FastAPI verifies this JWT on every protected request. We do not implement a custom admin auth system.
- **Device Authentication**: Devices are not users. They authenticate via a unique `Device ID` and a securely hashed `API Key`. FastAPI validates both before accepting telemetry ingestion.

## 3. Database

- **Primary Store**: Supabase PostgreSQL.
- **Tooling**: SQLAlchemy for ORM and Alembic for migrations.
- **Identifiers**: UUIDs are used as primary keys for all entities (Devices, Customers, Users).

## 4. Layered Architecture (DDD-Inspired)

- **Routers (`api/v1`)**: Handle HTTP requests and responses only.
- **Services (`services/`)**: Contain all business logic.
- **Repositories (`repositories/`)**: Handle all database access.
- **Workers (`workers/`)**: Handle background jobs (e.g., offline detection).
