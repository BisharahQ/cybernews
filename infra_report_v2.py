#!/usr/bin/env python3

def hr(title=""):
    if title:
        print(f"\n{'=' * 75}")
        print(f"  {title}")
        print(f"{'=' * 75}")
    else:
        print("-" * 75)

# ============================================================
# INPUT PARAMETERS — UPDATED
# ============================================================
AGENTS = 47
AVG_EPS = 252
PEAK_EPS = 327
DAILY_GB = 16.1
RETENTION_HOT_WARM = 90   # 3 months live in ES
RETENTION_GLACIER = 275   # rest of year in S3 Glacier Deep Archive
RETENTION_TOTAL = RETENTION_HOT_WARM + RETENTION_GLACIER  # 365

HOT_DAYS = 30
WARM_DAYS = 60            # 30-90d
GLACIER_DAYS = RETENTION_GLACIER

GROWTH_PCT = 15
REPLICA_HOT = 1
REPLICA_WARM = 0

# Compression ratios
WARM_COMPRESSION = 0.75   # force-merge + best_compression ~25% savings
GLACIER_COMPRESSION = 0.45  # deep archive with gzip/zstd ~55% savings

growth = GROWTH_PCT / 100
avg_daily = DAILY_GB * (1 + growth / 2)  # mid-year average

# ============================================================
# STORAGE MATH
# ============================================================
hot_raw = avg_daily * HOT_DAYS
hot_total = hot_raw * (1 + REPLICA_HOT)

warm_raw = avg_daily * WARM_DAYS * WARM_COMPRESSION
warm_total = warm_raw * (1 + REPLICA_WARM)

glacier_raw = avg_daily * GLACIER_DAYS * GLACIER_COMPRESSION
glacier_total = glacier_raw  # no replicas in glacier

es_live_storage = hot_total + warm_total  # what ES cluster actually holds
total_all = es_live_storage + glacier_total

peak_daily = DAILY_GB * (1 + growth)

# ============================================================
# REPORT
# ============================================================

hr("ES8 ON K3s - REVISED: 3 MONTHS LIVE + S3 GLACIER DEEP ARCHIVE")
print(f"  Date: 2026-03-05")
print(f"  Scenario: Moderate (47 agents, Endpoint+System+Windows)")
print(f"  Live retention: {RETENTION_HOT_WARM} days in ES (hot+warm)")
print(f"  Archive: {GLACIER_DAYS} days in S3 Glacier Deep Archive")

# ============================================================
hr("1. STORAGE BREAKDOWN")
# ============================================================

print(f"""
  +------------------+-------+---------+----------+----------+------------------+
  | Tier             | Days  | Raw GB  | Compress | Total GB | Where            |
  +------------------+-------+---------+----------+----------+------------------+
  | Hot (NVMe/SSD)   | 0-{HOT_DAYS}  | {avg_daily*HOT_DAYS:>7.0f} | none     | {hot_total:>8.0f} | ES cluster (SSD) |
  | Warm (SSD)       | {HOT_DAYS}-{HOT_DAYS+WARM_DAYS} | {avg_daily*WARM_DAYS:>7.0f} | 25%      | {warm_total:>8.0f} | ES cluster (SSD) |
  +------------------+-------+---------+----------+----------+------------------+
  | ES LIVE TOTAL    | 0-{RETENTION_HOT_WARM}  |         |          | {es_live_storage:>8.0f} | On-cluster        |
  +------------------+-------+---------+----------+----------+------------------+
  | Glacier Deep Arc | {RETENTION_HOT_WARM}-{RETENTION_TOTAL} | {avg_daily*GLACIER_DAYS:>7.0f} | 55%      | {glacier_total:>8.0f} | S3 Glacier DA     |
  +------------------+-------+---------+----------+----------+------------------+
  | GRAND TOTAL      | 1 yr  |         |          | {total_all:>8.0f} |                   |
  +------------------+-------+---------+----------+----------+------------------+

  Key insight: ES cluster only needs {es_live_storage:.0f} GB ({es_live_storage/1024:.1f} TB) of local disk
  vs {total_all:.0f} GB ({total_all/1024:.1f} TB) total with archive
""")

# ============================================================
hr("2. REVISED CLUSTER — SMALLER FOOTPRINT")
# ============================================================

# With only 90 days live, we need much less local storage
# Hot: 1038 GB (same)
# Warm: only 60 days * 17.3 avg * 0.75 = ~779 GB
# No cold tier in ES at all — straight to Glacier

hot_per_node = 400
n_hot = 3
warm_per_node = 500
n_warm = 2  # could even be 1 with large disk

print(f"""
  TOPOLOGY (same as before, but LESS DISK on warm, NO cold nodes):

  +------------------------------------------------------------------+
  |                    K3s CLUSTER                                    |
  |                                                                    |
  |  [Master-1]  [Master-2]  [Master-3]   K3s + ES dedicated masters |
  |   2 vCPU      2 vCPU      2 vCPU                                 |
  |   4 GB RAM    4 GB RAM    4 GB RAM                                |
  |   50 GB SSD   50 GB SSD   50 GB SSD                              |
  |                                                                    |
  |  [Hot-1]     [Hot-2]     [Hot-3]      ES hot data + ingest       |
  |   8 vCPU      8 vCPU      8 vCPU      + Kibana/Fleet co-located  |
  |   32 GB RAM   32 GB RAM   32 GB RAM                               |
  |   400 GB NVMe 400 GB NVMe 400 GB NVMe                            |
  |                                                                    |
  |  [Warm-1]    [Warm-2]                 ES warm data (read-only)   |
  |   4 vCPU      4 vCPU                                              |
  |   16 GB RAM   16 GB RAM                                           |
  |   500 GB SSD  500 GB SSD                                          |
  +------------------------------------------------------------------+
  |  [S3 Glacier Deep Archive]            9 months of snapshots      |
  |   ~{glacier_total:.0f} GB compressed                                     |
  |   Retrieved in 12-48 hours (bulk restore)                         |
  +------------------------------------------------------------------+

  TOTAL: 8 nodes (3 master + 3 hot + 2 warm)
""")

# ============================================================
hr("3. NODE SPECS — REVISED")
# ============================================================

masters_cpu = 3 * 2
masters_ram = 3 * 4
masters_disk = 3 * 50

hot_cpu = 3 * 8
hot_ram = 3 * 32
hot_disk = 3 * 400

warm_cpu = 2 * 4
warm_ram = 2 * 16
warm_disk = 2 * 500

total_cpu = masters_cpu + hot_cpu + warm_cpu
total_ram = masters_ram + hot_ram + warm_ram
total_disk = masters_disk + hot_disk + warm_disk

print(f"""
  +----------------+-------+--------+--------+------------+-------------------+
  | Role           | Count | vCPU   | RAM    | Local Disk | ES Heap           |
  +----------------+-------+--------+--------+------------+-------------------+
  | K3s/ES Master  |   3   | 2 ea   |  4 GB  |  50 GB SSD | 1.5 GB            |
  | Hot Data       |   3   | 8 ea   | 32 GB  | 400 GB NVMe| 16 GB             |
  | Warm Data      |   2   | 4 ea   | 16 GB  | 500 GB SSD | 8 GB              |
  +----------------+-------+--------+--------+------------+-------------------+
  | TOTALS         |   8   | {total_cpu:>3}    | {total_ram:>3} GB | {total_disk/1000:.1f} TB      |                   |
  +----------------+-------+--------+--------+------------+-------------------+

  vs previous plan:
    Local disk: {total_disk/1000:.1f} TB (was 3.0 TB) — saved {(3000-total_disk)/1000:.1f} TB
    RAM: same {total_ram} GB
    vCPU: same {total_cpu}
    No cold nodes needed (Glacier replaces them)
""")

# ============================================================
hr("4. S3 GLACIER DEEP ARCHIVE — HOW IT WORKS")
# ============================================================

monthly_glacier_gb = avg_daily * 30 * GLACIER_COMPRESSION
glacier_cost_per_gb = 0.00099  # S3 Glacier Deep Archive per GB/month
glacier_monthly_cost = glacier_total * glacier_cost_per_gb
glacier_restore_cost_per_gb = 0.02  # bulk restore

# S3 standard for snapshot repo (temporary staging)
s3_standard_staging = avg_daily * 2  # 2 days staging buffer
s3_staging_cost = s3_standard_staging * 0.023

print(f"""
  LIFECYCLE:
    Day 0-30:   HOT tier in ES (NVMe, 1 replica, full-speed search)
    Day 30-90:  WARM tier in ES (SSD, 0 replicas, force-merged, searchable)
    Day 90:     ILM triggers snapshot to S3 Standard (staging)
    Day 91:     S3 Lifecycle rule moves snapshot to Glacier Deep Archive
    Day 365:    Delete from Glacier

  SNAPSHOT FLOW:
    ES ILM --> snapshot to S3 Standard bucket --> S3 Lifecycle --> Glacier DA
                (staging, ~2 days)               (auto-transition)

  S3 BUCKET STRUCTURE:
    s3://watchwave-es-snapshots/
      /hot-staging/        <-- ES snapshot repo (S3 Standard, transient)
      /archive/            <-- Glacier Deep Archive (long-term)

  RETRIEVAL (when needed):
    1. Initiate S3 Glacier restore (Bulk: 12-48 hrs, Standard: 3-5 hrs)
    2. Once restored to S3 Standard, register as ES snapshot repo
    3. Restore specific indices into ES warm/hot tier
    4. Query as normal, then delete when done

  IMPORTANT LIMITATIONS:
    - Glacier Deep Archive is NOT searchable directly
    - Minimum storage: 180 days (you pay for 180 days even if deleted early)
    - Retrieval takes 12-48 hours (bulk) or 3-5 hours (standard)
    - Good for: compliance, forensics, incident investigation
    - NOT good for: daily queries, dashboards, real-time alerts
""")

# ============================================================
hr("5. COST BREAKDOWN — REVISED")
# ============================================================

# Glacier Deep Archive pricing (us-east-1)
glacier_da_per_gb_month = 0.00099
glacier_total_monthly = glacier_total * glacier_da_per_gb_month

# S3 Standard staging (small, transient)
s3_staging_monthly = s3_standard_staging * 0.023

# Glacier restore costs (estimate 1 restore/month of 30 days data)
restore_monthly_gb = avg_daily * 30 * GLACIER_COMPRESSION
restore_cost = restore_monthly_gb * glacier_restore_cost_per_gb

print(f"""
  +----------------------------+-------------------------------------------+
  | Component                  | Monthly Cost                              |
  +----------------------------+-------------------------------------------+
  | COMPUTE (OCI VMs)          |                                           |
  |   3x Master (2 OCPU, 4GB) | $75                                       |
  |   3x Hot (8 OCPU, 32GB)   | $450                                      |
  |   2x Warm (4 OCPU, 16GB)  | $150                                      |
  +----------------------------+-------------------------------------------+
  | BLOCK STORAGE (OCI)        |                                           |
  |   3x 50GB  (masters)       | $9                                        |
  |   3x 400GB (hot NVMe)     | $75                                       |
  |   2x 500GB (warm SSD)     | $60                                       |
  +----------------------------+-------------------------------------------+
  | S3 / OBJECT STORAGE        |                                           |
  |   Glacier Deep Archive     |                                           |
  |     {glacier_total:.0f} GB @ $0.00099/GB  | ${glacier_total_monthly:>6.2f}                              |
  |   S3 Standard (staging)    |                                           |
  |     {s3_standard_staging:.0f} GB @ $0.023/GB    | ${s3_staging_monthly:>6.2f}                               |
  |   Restore (1x/mo, 30 days)|                                           |
  |     {restore_monthly_gb:.0f} GB @ $0.02/GB    | ${restore_cost:>6.2f}                              |
  +----------------------------+-------------------------------------------+
  | NETWORKING / LB            | $20                                       |
  +----------------------------+-------------------------------------------+

  MONTHLY TOTAL:
    Compute:         $675
    Block storage:   $144
    S3 Glacier DA:   ${glacier_total_monthly:.2f}
    S3 staging:      ${s3_staging_monthly:.2f}
    S3 restore:      ${restore_cost:.2f} (only if restoring)
    Networking:      $20
    -------------------------------------------------
    TOTAL:           ~$845-$860/month
    ANNUAL:          ~$10,100-$10,300/year
""")

# ============================================================
hr("6. COST COMPARISON: OLD vs NEW vs GLACIER PLAN")
# ============================================================

print(f"""
  +-----------------------------+-----------+-----------+-----------+
  | Item                        | Current   | Plan v1   | Plan v2   |
  |                             | (Wazuh)   | (S3 cold) | (Glacier) |
  +-----------------------------+-----------+-----------+-----------+
  | Live data in ES             | all time  | 1 year    | 3 months  |
  | Archive                     | none      | S3 cold   | Glacier DA|
  | ES local disk               | ~640 GB   | 3.0 TB    | {total_disk/1000:.1f} TB    |
  | Object storage              | none      | 2.3 TB    | {glacier_total/1024:.1f} TB    |
  | Total nodes                 | 1         | 8         | 8         |
  | Monthly cost                | ~$175     | ~$1,050   | ~$850     |
  | Annual cost                 | ~$2,100   | ~$12,600  | ~$10,200  |
  | Search last 3 months        | instant   | instant   | instant   |
  | Search 3-12 months ago      | instant   | instant   | 12-48 hrs |
  | HA / fault tolerance        | none      | yes       | yes       |
  +-----------------------------+-----------+-----------+-----------+

  SAVINGS vs Plan v1:  ~$200/month (~$2,400/year)
  Tradeoff: Searching data older than 3 months requires 12-48hr restore
""")

# ============================================================
hr("7. ILM POLICY — REVISED")
# ============================================================

print(f"""
  Policy: "watchwave-ilm-v2"

  +----------+-----+------------------------------------------------------+
  | Phase    | Day | Actions                                              |
  +----------+-----+------------------------------------------------------+
  | Hot      | 0   | rollover: max_age=1d OR max_size=50GB                |
  |          |     | replicas: 1, priority: 100                           |
  |          |     | index.codec: default (LZ4)                           |
  +----------+-----+------------------------------------------------------+
  | Warm     | 30  | allocate: require.data=warm                          |
  |          |     | replicas: 0                                           |
  |          |     | force_merge: max_num_segments=1                      |
  |          |     | index.codec: best_compression (DEFLATE)              |
  |          |     | shrink: 1 primary shard                              |
  |          |     | priority: 50                                          |
  +----------+-----+------------------------------------------------------+
  | Snapshot | 85  | snapshot to S3 Standard repo                         |
  |          |     | wait_for_snapshot: true                               |
  |          |     | (S3 Lifecycle auto-transitions to Glacier DA in 5d)  |
  +----------+-----+------------------------------------------------------+
  | Delete   | 90  | delete index from ES (data safe in Glacier)          |
  |          |     | (5-day overlap ensures snapshot completes)            |
  +----------+-----+------------------------------------------------------+
  | Glacier  | 91+ | Managed by S3 Lifecycle, NOT by ES                   |
  |          |     | Auto-delete at day 365 via S3 expiration rule        |
  +----------+-----+------------------------------------------------------+

  S3 Lifecycle Policy:
    - Transition to Glacier Deep Archive: 5 days after upload
    - Expire/delete: 280 days after upload (= day 365 from ingest)
""")

# ============================================================
hr("8. DISASTER RECOVERY & RESTORE PROCEDURE")
# ============================================================

print(f"""
  SCENARIO: Need to investigate incident from 6 months ago

  Step 1: Identify date range needed
    $ curl -s 'https://es:9200/_snapshot/glacier-repo/_all' | jq '.snapshots[].indices'

  Step 2: Initiate Glacier restore (AWS CLI or OCI equivalent)
    $ aws s3api restore-object \\
        --bucket watchwave-es-snapshots \\
        --key archive/snap-2025.09.15/... \\
        --restore-request Days=7,GlacierJobParameters={{Tier=Bulk}}

    Wait 12-48 hours (Bulk) or 3-5 hours (Standard, costs more)

  Step 3: Register temporary snapshot repo in ES
    PUT _snapshot/temp-restore
    {{
      "type": "s3",
      "settings": {{
        "bucket": "watchwave-es-snapshots",
        "base_path": "restored/",
        "readonly": true
      }}
    }}

  Step 4: Restore specific indices
    POST _snapshot/temp-restore/snap-2025.09.15/_restore
    {{
      "indices": "watchwave-alerts-4.x-2025.09.15",
      "rename_pattern": "(.+)",
      "rename_replacement": "restored-$1"
    }}

  Step 5: Query restored data, then clean up
    DELETE restored-watchwave-alerts-4.x-2025.09.15

  RESTORE COST ESTIMATE (30 days of data):
    Glacier Bulk restore: {restore_monthly_gb:.0f} GB x $0.02 = ${restore_monthly_gb * 0.02:.2f}
    S3 GET requests: ~$5-10
    Total per restore: ~${restore_monthly_gb * 0.02 + 7.5:.0f}
""")

# ============================================================
hr("9. FINAL SUMMARY — AT A GLANCE")
# ============================================================

print(f"""
  +------------------------+--------------------------------------------+
  | Kubernetes             | K3s (HA, 3 masters)                        |
  | ES Operator            | ECK 2.14+                                  |
  | ES Version             | 8.17+ (latest stable)                      |
  +------------------------+--------------------------------------------+
  | Total Nodes            | 8 (3 master + 3 hot + 2 warm)             |
  | Total vCPUs            | {total_cpu}                                         |
  | Total RAM              | {total_ram} GB                                      |
  | Total Local Disk       | {total_disk/1000:.1f} TB                                    |
  +------------------------+--------------------------------------------+
  | Live Data (ES)         | 3 months ({RETENTION_HOT_WARM} days)                        |
  |   Hot tier             | {HOT_DAYS} days, {hot_total:.0f} GB (1 replica, NVMe)       |
  |   Warm tier            | {WARM_DAYS} days, {warm_total:.0f} GB (0 replicas, SSD)      |
  +------------------------+--------------------------------------------+
  | Archive (Glacier DA)   | 9 months ({GLACIER_DAYS} days)                       |
  |   Size                 | {glacier_total:.0f} GB ({glacier_total/1024:.1f} TB) compressed           |
  |   Restore time         | 12-48 hrs (Bulk) / 3-5 hrs (Standard)     |
  +------------------------+--------------------------------------------+
  | Avg EPS                | {AVG_EPS}                                         |
  | Peak EPS               | {PEAK_EPS}                                         |
  | Daily Ingestion        | {DAILY_GB} GB/day -> {peak_daily:.1f} GB/day EOY            |
  | 1-Year Total Data      | {total_all/1024:.1f} TB (live + archive)                |
  +------------------------+--------------------------------------------+
  | Monthly Cost           | ~$850                                      |
  | Annual Cost            | ~$10,200                                   |
  | HA / Fault Tolerance   | Survives 1 master + 1 data node failure   |
  +------------------------+--------------------------------------------+
""")
