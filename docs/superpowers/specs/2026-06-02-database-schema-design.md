# Database Schema Implementation Design

## Scope

Implement the local MySQL database schema for the CSCEC smart safety platform against:

- host: `127.0.0.1`
- port: `3306`
- database: `intelligent_security_platform`

The database already exists and is empty. This iteration creates the currently used core ORM tables, not every future planning table from the database design document.

## Table Set

Use the current SQLAlchemy ORM as the implementation baseline:

- `tenant`
- `project`
- `subcontractor`
- `worker`
- `hazard`
- `equipment`
- `project_risk_profile`
- `worker_risk_profile`
- `subcontractor_risk_profile`
- `rule_trigger_log`
- `safety_work_order`
- `agent_task_log`
- `metric_catalog`
- `agent_task_checkpoint`
- `profile_calc_detail`

This includes the MVP tables plus already-used second-phase tables for metrics and Agent checkpoints.

## Migration Approach

Replace the empty Alembic initial migration with a deterministic metadata-based migration for the current model set. Alembic will create tables from the ORM metadata snapshot used by the application. Downgrade drops all tables in reverse dependency order.

Because the target database is currently empty, this is simpler and safer than creating a chain of ALTER migrations from the old demo schema.

## Runtime Configuration

Default backend DB URL changes to `intelligent_security_platform`.

`main.py` defaults:

- MySQL port preference: `3306`, then `3307` only as fallback;
- database name: `intelligent_security_platform`;
- `RESET_DATABASE_ON_START=0` by default.

If a developer needs to recreate demo data, they can explicitly set `RESET_DATABASE_ON_START=1`.

## Seed Strategy

Make `scripts/seed_demo_data.py` idempotent: if demo tenant data already exists, skip insertion. This keeps `main.py` safe to run repeatedly when reset is disabled.

## Verification

Run:

- Alembic upgrade against `intelligent_security_platform`;
- seed script twice to verify idempotency;
- schema inspection to confirm tables exist;
- backend tests;
- compileall;
- HTTP smoke for health and metrics.

