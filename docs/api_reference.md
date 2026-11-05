# REST API Reference: Multi-Cloud Disaster Recovery Platform

Base URL: `/api/v1`

All protected endpoints require an `Authorization: Bearer <JWT_TOKEN>` header obtained via the login endpoint.

---

## 1. Authentication & Users

### `POST /api/v1/auth/login`
Authenticates a user and issues an access token.

- **Request Format**: `OAuth2PasswordRequestForm` (Form-URL-Encoded)
  - `username` (string, required): E.g. `admin`
  - `password` (string, required): E.g. `admin12345`
- **Response `200 OK`**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "role": "admin",
    "expires_in_minutes": 1440
  }
  ```

### `GET /api/v1/auth/me`
Retrieves details of the currently authenticated user.

---

## 2. File Management & Object Manifest

### `GET /api/v1/files/`
Lists all managed objects, their version trees, and cross-cloud replicas.

- **Query Parameters**:
  - `skip` (int, default `0`)
  - `limit` (int, default `100`)
- **Response `200 OK`**:
  ```json
  {
    "total": 42,
    "items": [
      {
        "id": "file-uuid-001",
        "owner_id": "user-uuid-admin",
        "filename": "quarterly_ledger.parquet",
        "storage_key": "finance/quarterly_ledger.parquet",
        "file_size_bytes": 41943040,
        "content_type": "application/octet-stream",
        "sha256_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        "priority": "CRITICAL",
        "access_frequency_tier": "FREQUENT",
        "is_deleted": false,
        "created_at": "2026-11-04T18:00:00Z",
        "versions": [
          {
            "id": "ver-001",
            "version_num": 1,
            "aws_version_id": "s3-v1-41943040",
            "gcp_generation_id": "1712398492019",
            "size_bytes": 41943040,
            "sha256_hash": "9f86d081...",
            "is_current": true
          }
        ],
        "replicas": [
          {
            "id": "rep-001",
            "provider_id": "gcp-storage-replica",
            "replica_uri": "gs://acft-dr-secondary-replica/finance/quarterly_ledger.parquet",
            "is_verified": true,
            "replication_latency_ms": 1840.5,
            "transfer_cost_usd": 0.0036
          }
        ]
      }
    ]
  }
  ```

### `POST /api/v1/files/upload`
Uploads a new object to primary storage (AWS S3) and dispatches it to the asynchronous replication pipeline.

- **Request Format**: `multipart/form-data`
  - `file` (Binary, required)
  - `priority` (string, default `MEDIUM`): `CRITICAL` | `HIGH` | `MEDIUM` | `LOW`
  - `access_frequency_tier` (string, default `FREQUENT`): `FREQUENT` | `INFREQUENT` | `ARCHIVE`
  - `tags` (string, optional): E.g. `audit, finance`
- **Response `201 Created`**:
  ```json
  {
    "file_id": "file-uuid-001",
    "version_id": "ver-uuid-001",
    "filename": "quarterly_ledger.parquet",
    "storage_key": "uploads/quarterly_ledger.parquet",
    "file_size_bytes": 41943040,
    "sha256_hash": "9f86d081...",
    "priority": "CRITICAL",
    "upload_status": "UPLOADED_TO_PRIMARY",
    "replication_job_id": "job-uuid-101",
    "message": "File uploaded to AWS S3. Dispatched to asynchronous replication pipeline."
  }
  ```

### `GET /api/v1/files/{file_id}/download`
Streams the object payload. If AWS S3 is operational, reads from AWS S3. If AWS S3 is marked as `OUTAGE`, transparently reads from the verified GCP GCS replica.

### `DELETE /api/v1/files/{file_id}`
Soft-deletes the object metadata and deletes physical objects from both AWS S3 and GCP GCS buckets.

---

## 3. Disaster Recovery & Health

### `GET /api/v1/disaster-recovery/health`
Returns the operational health matrix of both cloud providers and the active read router routing state.

- **Response `200 OK`**:
  ```json
  {
    "timestamp": "2026-11-04T18:30:00Z",
    "primary_cloud": {
      "id": "aws-s3-primary",
      "name": "AWS S3 (US-East-1)",
      "is_primary": true,
      "status": "HEALTHY",
      "current_latency_ms": 42.4
    },
    "secondary_cloud": {
      "id": "gcp-storage-replica",
      "name": "GCS Standard (US-Central-1)",
      "is_primary": false,
      "status": "HEALTHY",
      "current_latency_ms": 58.1
    },
    "active_read_provider": "AWS_S3",
    "failover_active": false,
    "simulation_mode": true,
    "consecutive_failures": 0
  }
  ```

### `POST /api/v1/disaster-recovery/failover`
Forces an immediate failover, rerouting all reads to GCP GCS and recording an audit event.

### `POST /api/v1/disaster-recovery/reconcile`
Executes post-recovery bidirectional synchronization from GCS back to AWS S3.

---

## 4. Replication Policies & Jobs

### `GET /api/v1/replication/policies`
Lists all configured replication policies, active strategy types, and scoring weights.

### `PUT /api/v1/replication/policies/{policy_id}`
Updates policy threshold parameters, target RTO/RPO, budget caps, and composite scoring weights.

### `GET /api/v1/replication/jobs`
Lists asynchronous replication jobs, status (`PENDING`, `REPLICATING`, `COMPLETED`, `SKIPPED`, `FAILED`), decision scores, and rationales.

---

## 5. Cost Analytics & Estimator

### `GET /api/v1/cost/summary`
Returns an audited breakdown of AWS storage, GCP storage, cross-cloud egress fees, cumulative net savings vs full replication baseline, and budget utilization.

### `POST /api/v1/cost/estimate`
Pre-calculates projected replication costs for an arbitrary payload size, priority tier, and retention window.

