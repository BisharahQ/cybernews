#!/usr/bin/env python3

# ============================================================
# CURRENT BASELINE (from cluster data)
# ============================================================
# Wazuh monitoring: ~4,512 docs/day
# Wazuh reports agent status every ~15 min = 96 checks/day
agents = 4512 / 96

# Current watchwave-alerts (last 7 days)
avg_docs_day = 7_254_696
avg_gb_day = 5.30
avg_eps = 84
peak_eps = 108
avg_doc_size_kb = (avg_gb_day * 1024 * 1024) / avg_docs_day

print("=" * 70)
print("CURRENT BASELINE (Wazuh + WatchWave)")
print("=" * 70)
print(f"Agents:               ~{agents:.0f}")
print(f"Avg docs/day:         {avg_docs_day:>12,}")
print(f"Avg GB/day:           {avg_gb_day:>12.2f} GB")
print(f"Avg EPS:              {avg_eps:>12} EPS")
print(f"Peak EPS:             {peak_eps:>12} EPS")
print(f"Avg doc size:         {avg_doc_size_kb:>12.2f} KB")
print()

# ============================================================
# WHY VOLUME CHANGES WITH ELASTIC 8 + FLEET
# ============================================================
# Wazuh  = agent-side decode + rule matching -> sends ALERTS ONLY
# Elastic Agent + Fleet = sends RAW EVENTS to ES -> detection engine
#   runs server-side -> generates alerts
#
# Per-agent typical volumes with Elastic integrations:
#   Endpoint Security:  50-200 MB/day (process/file/network/registry)
#   System integration: 10-50 MB/day (auth, syslog, metrics)
#   Windows Events:     20-80 MB/day
#   Network:            50-200 MB/day (if enabled)
#   Detection alerts:   5-20 MB/day
# ============================================================

n_agents = int(agents)

print("=" * 70)
print("ES8 + FLEET + INTEGRATIONS - 3 SCENARIOS (47 agents)")
print("=" * 70)

scenarios = [
    ("Conservative (alerts-focused, minimal raw events)", 150, 1.2, 10),
    ("Moderate (Endpoint + System + Windows integrations)", 350, 3.0, 15),
    ("Full Telemetry (all integrations + network)", 600, 6.0, 20),
]

for name, per_agent_mb, eps_mult, growth_pct in scenarios:
    daily_gb = (n_agents * per_agent_mb) / 1024
    daily_docs = int(avg_docs_day * eps_mult)
    daily_eps = daily_docs / 86400
    peak_daily_eps = daily_eps * 1.3

    growth = growth_pct / 100
    yearly_gb = 0
    for month in range(12):
        monthly_factor = 1 + (growth * month / 12)
        yearly_gb += daily_gb * monthly_factor * 30.44

    # Tiering
    hot_days = 30
    warm_days = 60
    cold_days = 275

    hot_gb = daily_gb * hot_days * (1 + growth) * 2
    warm_gb = daily_gb * warm_days * (1 + growth / 2) * 1
    cold_gb = daily_gb * cold_days * 0.55
    total_tiered_gb = hot_gb + warm_gb + cold_gb

    raw_1yr_1rep = yearly_gb * 2

    print(f"\n--- {name} ---")
    print(f"  Per agent:          {per_agent_mb:>6} MB/day")
    print(f"  Daily ingestion:    {daily_gb:>8.1f} GB/day")
    print(f"  Daily docs:         {daily_docs:>12,}")
    print(f"  Avg EPS:            {daily_eps:>8,.0f} EPS")
    print(f"  Peak EPS (1.3x):    {peak_daily_eps:>8,.0f} EPS")
    print(f"  YoY growth:         {growth_pct:>6}%")
    print(f"  ---")
    print(f"  1-Year RAW storage: {yearly_gb:>8,.0f} GB  ({yearly_gb / 1024:,.1f} TB)")
    print(f"  1-Year w/ 1 replica:{raw_1yr_1rep:>8,.0f} GB  ({raw_1yr_1rep / 1024:,.1f} TB)")
    print(f"  ---")
    print(f"  TIERED STORAGE (recommended for EKS):")
    print(f"    Hot  (30d, 1 rep):       {hot_gb:>8,.0f} GB")
    print(f"    Warm (60d, 0 rep):       {warm_gb:>8,.0f} GB")
    print(f"    Cold (275d, compressed): {cold_gb:>8,.0f} GB")
    print(f"    TOTAL tiered:            {total_tiered_gb:>8,.0f} GB  ({total_tiered_gb / 1024:,.1f} TB)")

# ============================================================
# EKS SIZING RECOMMENDATION
# ============================================================
print()
print("=" * 70)
print("EKS SIZING RECOMMENDATION (Moderate scenario - 47 agents)")
print("=" * 70)

mod_daily_gb = (n_agents * 350) / 1024
cold_s3_gb = int(n_agents * 350 * 275 * 0.55 / 1024)
cold_s3_cost = int(cold_s3_gb * 0.023)

print(f"""
  MASTER NODES (dedicated):
    3x m6g.large (2 vCPU, 8 GB RAM)
    EBS gp3: 20 GB each

  HOT DATA NODES (ingest + recent search):
    3x r6g.xlarge (4 vCPU, 32 GB RAM)
    EBS gp3: 300 GB each = 900 GB total
    Handles: {mod_daily_gb:.1f} GB/day ingest + 30 days hot

  WARM DATA NODES:
    2x r6g.large (2 vCPU, 16 GB RAM)
    EBS gp3: 500 GB each = 1 TB total
    Handles: 60 days warm tier

  COLD/FROZEN (S3-backed searchable snapshots):
    S3 bucket: ~{cold_s3_gb} GB for 275 days
    S3 cost: ~${cold_s3_cost}/month

  FLEET SERVER:
    1x m6g.large (2 vCPU, 8 GB)

  KIBANA:
    1x m6g.large (2 vCPU, 8 GB)

  ESTIMATED MONTHLY COST (Moderate scenario):
    EKS control plane:    $73
    EC2 (data+master):    ~$600-800
    EBS storage:          ~$150-200
    S3 cold storage:      ~${cold_s3_cost}
    Data transfer:        ~$50-100
    -----------------------------------------------
    TOTAL:                ~$1,000-1,300/month
""")

# ============================================================
# SUMMARY TABLE
# ============================================================
print("=" * 70)
print("SUMMARY - 1 YEAR PROJECTIONS")
print("=" * 70)
print(f"{'Scenario':<45} {'EPS':>8} {'GB/day':>8} {'1yr TB':>8} {'Tiered TB':>10}")
print("-" * 70 + "-" * 12)
print(f"{'Current (Wazuh alerts only)':<45} {'84':>8} {'5.3':>8} {'1.9':>8} {'N/A':>10}")

for name, per_agent_mb, eps_mult, growth_pct in scenarios:
    daily_gb = (n_agents * per_agent_mb) / 1024
    daily_eps = int(avg_docs_day * eps_mult) / 86400
    growth = growth_pct / 100
    yearly_gb = 0
    for month in range(12):
        monthly_factor = 1 + (growth * month / 12)
        yearly_gb += daily_gb * monthly_factor * 30.44
    hot_gb = daily_gb * 30 * (1 + growth) * 2
    warm_gb = daily_gb * 60 * (1 + growth / 2)
    cold_gb = daily_gb * 275 * 0.55
    tiered = (hot_gb + warm_gb + cold_gb) / 1024
    short = name.split("(")[0].strip()
    print(f"{short:<45} {daily_eps:>8,.0f} {daily_gb:>8.1f} {yearly_gb / 1024:>8.1f} {tiered:>10.1f}")
