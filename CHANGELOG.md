# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Milestone 3A**: Device Platform (Backend). Implemented robust CRUD for Customers and Devices with advanced pagination, searching, and API key provisioning functionality.

## [0.2.0] - Milestone 2
### Added
- Database & Domain Design implemented via SQLAlchemy 2.0.
- Pydantic V2 schemas for entity validation.
- Alembic configured for async migrations.
- Complete set of initial domain models: Users, Customers, Devices, Telemetry, and Alerts.
- Portable standard PostgreSQL UUIDs, Enums, and JSONB implementation.

## [0.1.0] - Milestone 1
### Added
- Initial project foundation using `uv` for backend dependency management.
- Backend structured with FastAPI, SQLAlchemy, Alembic, structured logging, and configuration management via Pydantic settings.
- Frontend initialized using React, Vite, TypeScript, and Tailwind CSS.
- Docker Compose configuration for local development.
