# Relational Database Schema Design (PostgreSQL)

## 1. Entity-Relationship Overview

The platform uses PostgreSQL 15 as its ACID-compliant source of truth for file metadata, multi-cloud version manifests, asynchronous task tracking, and disaster recovery audit events.

```mermaid
erDiagram
    users ||--o{ files : "owns"
    users ||--o{ audit_logs : "triggers"
    files ||--|{ file_versions : "tracks"
    files ||--o{ file_replicas : "replicated_as"
    files ||--o{ replication_jobs : "queued_for"
    files ||--o{ cost_records : "generates"
    file_versions ||--o{ file_replicas : "has_replica"
    replication_policies ||--o{ replication_jobs : "governs"
    cloud_providers ||--o{ file_replicas : "hosts"
    cloud_providers ||--o{ cloud_health_logs : "logged_by"
    cloud_providers ||--o{ disaster_recovery_events : "affected_in"
    experiment_runs ||--o{ experiment_results : "yields"

    users {
        string id PK
        string email UK
        string username UK
        string hashed_password
        string role
        boolean is_active
        datetime created_at
    }

    files {
        string id PK
        string owner_id FK
        string filename
        string storage_key UK
        bigint file_size_bytes
        string content_type
        string sha256_hash
        string priority
        string access_frequency_tier
        boolean is_deleted
        datetime created_at
        datetime updated_at
    }

    file_versions {
        string id PK
        string file_id FK
        integer version_num
        string aws_version_id
        string gcp_generation_id
        bigint size_bytes
        string sha256_hash
        boolean is_current
        datetime created_at
    }

    file_replicas {
        string id PK
        string file_id FK
        string version_id FK
        string provider_id FK
        string replica_uri
        string sha256_hash
        boolean is_verified
        float replication_latency_ms
        float transfer_cost_usd
        datetime created_at
    }

    replication_policies {
        string id PK
        string name UK
        string strategy_type
        integer target_rpo_seconds
        integer target_rto_seconds
        float max_budget_monthly_usd
        string weights_json
        float threshold_score
        boolean is_active
    }

    replication_jobs {
        string id PK
        string file_id FK
        string version_id FK
        string policy_id FK
        string status
        float decision_score
        string decision_reason
        string idempotency_key UK
        integer retry_count
        datetime scheduled_at
    }

    disaster_recovery_events {
        string id PK
        string event_type
        string failed_provider_id FK
        string failover_provider_id FK
        float rto_seconds
        float rpo_seconds
        integer affected_files_count
        integer reconciled_files_count
        datetime created_at
    }
```

---

## 2. Table Specifications & Indexes

### 1. `users`
- Stores system operators and research evaluators with bcrypt passwords.
- **Indexes**: `ix_users_username` (unique), `ix_users_email` (unique).

### 2. `cloud_providers`
- Stores endpoints and configurations for primary AWS S3 and secondary GCP GCS.
- **Indexes**: `ix_cloud_providers_name` (unique).

### 3. `files`
- Canonical metadata manifest for every uploaded object.
- **Indexes**: `ix_files_storage_key` (unique), `ix_files_owner_id`, `ix_files_priority`.

### 4. `file_versions`
- Implements object version history tracking both `aws_version_id` (string) and `gcp_generation_id` (integer string).
- **Constraints**: Composite unique index on `(file_id, version_num)`.

### 5. `file_replicas`
- Secondary cloud replicas verified with cryptographic SHA-256 hashes.
- **Indexes**: `ix_file_replicas_file_id`, `ix_file_replicas_provider_id`, `ix_file_replicas_is_verified`.

### 6. `replication_policies`
- Governs policy thresholds, target RTO/RPO SLA constraints, and JSON weight configurations.
- **Fields**: `threshold_score`, `max_budget_monthly_usd`, `weights_json`.

### 7. `replication_jobs`
- Asynchronous task ledger with idempotency keys to prevent duplicate Celery worker execution.
- **Indexes**: `ix_replication_jobs_idempotency_key` (unique), `ix_replication_jobs_status`.

### 8. `disaster_recovery_events`
- Immutable event audit log of failover triggers, chaos simulations, RTO/RPO metrics, and post-recovery reconciliations.
- **Indexes**: `ix_dr_events_event_type`, `ix_dr_events_created_at`.

### 9. `cost_records`
- Audited accounting of AWS storage, GCP storage, egress transfer charges, and API fees.

### 10. `experiment_runs` & `experiment_results`
- Persistent benchmark history comparing Full, Priority, and Cost-Aware Adaptive strategies.

### 11. `audit_logs`
- Regulatory audit trail capturing user IP addresses, actions, and timestamps.

---

## 3. Database Migrations
Migrations are maintained via **Alembic**:
- Initial migration script: `backend/alembic/versions/2026_11_04_1749-6081e039d877_initial_schema.py`
- Executable via: `alembic upgrade head`

