#!/usr/bin/env python3

def hr(title=""):
    if title:
        print(f"\n{'=' * 75}")
        print(f"  {title}")
        print(f"{'=' * 75}")
    else:
        print("-" * 75)

# ============================================================
# INPUT PARAMETERS
# ============================================================
AGENTS = 47
AVG_EPS = 252
PEAK_EPS = 327
DAILY_GB = 16.1
RETENTION_DAYS = 365
HOT_DAYS = 30
WARM_DAYS = 90
COLD_DAYS = RETENTION_DAYS - HOT_DAYS - WARM_DAYS  # 245
GROWTH_PCT = 15
REPLICA_HOT = 1
REPLICA_WARM = 0
REPLICA_COLD = 0
COLD_COMPRESSION = 0.55  # 45% savings with force-merge + best_compression

# ============================================================
# STORAGE MATH
# ============================================================
growth = GROWTH_PCT / 100
avg_daily_with_growth = DAILY_GB * (1 + growth / 2)  # mid-year average

hot_raw = avg_daily_with_growth * HOT_DAYS
hot_total = hot_raw * (1 + REPLICA_HOT)

warm_raw = avg_daily_with_growth * WARM_DAYS
warm_total = warm_raw * (1 + REPLICA_WARM)

cold_raw = avg_daily_with_growth * COLD_DAYS * COLD_COMPRESSION
cold_total = cold_raw * (1 + REPLICA_COLD)

total_storage = hot_total + warm_total + cold_total

# Peak day (end of year with growth)
peak_daily = DAILY_GB * (1 + growth)

# ============================================================
# REPORT
# ============================================================

hr("ELASTICSEARCH 8 ON KUBERNETES — FULL INFRASTRUCTURE REPORT")
print(f"  Date: 2026-03-05")
print(f"  Based on: Current cluster at 10.220.10.56 (Wazuh/WatchWave)")
print(f"  Target: ES 8.x + Fleet + Elastic Agent integrations")
print(f"  Scenario: Moderate (Endpoint + System + Windows integrations)")

# ============================================================
hr("1. K3S vs K8S RECOMMENDATION")
# ============================================================
print("""
  VERDICT: K3s (Recommended)

  Why K3s over K8s (kubeadm):
  +---------------------------+-------------------+-------------------+
  | Criteria                  | K3s               | K8s (kubeadm)     |
  +---------------------------+-------------------+-------------------+
  | Memory overhead per node  | ~512 MB           | ~1.5-2 GB         |
  | Control plane footprint   | Single binary     | Multiple daemons  |
  | Cert management           | Auto-rotate       | Manual/tooling    |
  | etcd                      | Embedded          | Separate cluster  |
  | Setup complexity          | 1 command          | 10+ steps         |
  | HA support                | Yes (embedded HA) | Yes               |
  | Helm/operators            | Full support      | Full support      |
  | Production ready          | Yes (CNCF cert)   | Yes               |
  | Best for                  | < 50 nodes        | 50+ nodes         |
  +---------------------------+-------------------+-------------------+

  With 47 agents and ~252 EPS, this is a small-medium deployment.
  K3s saves ~1 GB RAM per node and simplifies operations significantly.
  Use Rancher for UI management if needed.
""")

# ============================================================
hr("2. CAPACITY PLANNING — STORAGE")
# ============================================================
print(f"""
  Input Parameters:
    Agents:             {AGENTS}
    Avg EPS:            {AVG_EPS} (peak {PEAK_EPS})
    Daily ingestion:    {DAILY_GB} GB/day (current), {peak_daily:.1f} GB/day (end of year)
    Retention:          {RETENTION_DAYS} days (1 year)
    YoY growth:         {GROWTH_PCT}%

  Tier Breakdown:
  +------------------+-------+----------+---------+----------+-----------+
  | Tier             | Days  | Raw GB   | Replicas| Total GB | Storage   |
  +------------------+-------+----------+---------+----------+-----------+
  | Hot (SSD/NVMe)   |  {HOT_DAYS:>3}  | {hot_raw:>7.0f}  |    {REPLICA_HOT}    | {hot_total:>7.0f}   | Fast SSD  |
  | Warm (SSD/HDD)   |  {WARM_DAYS:>3}  | {warm_raw:>7.0f}  |    {REPLICA_WARM}    | {warm_total:>7.0f}   | Std SSD   |
  | Cold (S3/MinIO)  |  {COLD_DAYS:>3}  | {cold_raw:>7.0f}  |    {REPLICA_COLD}    | {cold_total:>7.0f}   | Object St |
  +------------------+-------+----------+---------+----------+-----------+
  | TOTAL            |  {RETENTION_DAYS}  |         |         | {total_storage:>7.0f}   |           |
  +------------------+-------+----------+---------+----------+-----------+

  Total 1-Year Storage: {total_storage:.0f} GB ({total_storage/1024:.1f} TB)
    Hot tier:   {hot_total:.0f} GB ({hot_total/1024:.1f} TB) — needs fast I/O
    Warm tier:  {warm_total:.0f} GB ({warm_total/1024:.1f} TB) — moderate I/O
    Cold tier:  {cold_total:.0f} GB ({cold_total/1024:.1f} TB) — S3-backed, cheapest
""")

# ============================================================
hr("3. CLUSTER ARCHITECTURE — NODE LAYOUT")
# ============================================================

# ES heap rule: 50% of RAM, max 31GB
# Hot nodes: need CPU for indexing + search, SSD for speed
# Warm nodes: less CPU, cheaper storage
# Cold: minimal CPU/RAM, S3-backed

# For 252 EPS and 16 GB/day, sizing:
hot_storage_per_node = 350  # GB SSD per hot node
n_hot = 3
warm_storage_per_node = 600
n_warm = 2
cold_storage_per_node = 1000
n_cold = 1  # + S3 for overflow

print(f"""
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    K3s CLUSTER TOPOLOGY                            │
  │                                                                     │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                         │
  │  │ Master-1 │  │ Master-2 │  │ Master-3 │  K3s Control Plane      │
  │  │ (server) │  │ (server) │  │ (server) │  + ES dedicated masters │
  │  └──────────┘  └──────────┘  └──────────┘                         │
  │       │              │              │                               │
  │  ┌────┴──────────────┴──────────────┴────┐                         │
  │  │          K3s Internal Network          │                         │
  │  └────┬──────┬──────┬──────┬──────┬──────┘                         │
  │       │      │      │      │      │                                 │
  │  ┌────┴─┐┌───┴──┐┌──┴───┐┌┴─────┐┌┴─────┐                        │
  │  │ Hot-1││ Hot-2││ Hot-3││Warm-1││Warm-2│  ES Data Nodes          │
  │  │ +Kib ││+Fleet││+Inges││      ││+Cold │  (K3s workers)          │
  │  └──────┘└──────┘└──────┘└──────┘└──────┘                         │
  └─────────────────────────────────────────────────────────────────────┘

  TOTAL: 8 nodes (3 masters + 5 workers)
""")

# ============================================================
hr("4. NODE SPECIFICATIONS — DETAILED")
# ============================================================

print("""
  ┌─────────────────────────────────────────────────────────────────────┐
  │ K3s MASTER / ES DEDICATED MASTER NODES (x3)                       │
  ├─────────────────────────────────────────────────────────────────────┤
  │ Role:       K3s server + ES dedicated master (no data)             │
  │ vCPU:       2                                                       │
  │ RAM:        4 GB                                                    │
  │   K3s:      ~512 MB                                                 │
  │   ES master: 1.5 GB heap + 1 GB OS                                 │
  │ Disk:       50 GB SSD (OS + etcd + ES metadata)                    │
  │ Network:    1 Gbps                                                  │
  │ OS:         Ubuntu 22.04 LTS / Rocky 9                             │
  │ Notes:      Lightweight — only manages cluster state               │
  │             3 nodes for HA quorum (tolerates 1 failure)            │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ HOT DATA NODES (x3)                                                │
  ├─────────────────────────────────────────────────────────────────────┤
  │ Role:       ES hot data + ingest pipeline                          │
  │ vCPU:       8                                                       │
  │ RAM:        32 GB                                                   │
  │   ES heap:  16 GB (-Xms16g -Xmx16g)                               │
  │   OS cache: 14 GB (filesystem cache for Lucene)                    │
  │   K3s/pods: 2 GB                                                    │
  │ Disk:       400 GB NVMe/SSD (gp3 or local NVMe)                   │
  │   Usable:   ~350 GB (85% watermark)                                │
  │   Holds:    ~22 days of data per node with 1 replica               │
  │ Network:    10 Gbps preferred (1 Gbps minimum)                     │
  │ IOPS:       3,000+ (gp3 baseline is fine)                          │""")

print(f"""  │ Throughput: 125 MB/s+ sustained                                    │
  │ Co-located: Hot-1 also runs Kibana pod                             │
  │             Hot-2 also runs Fleet Server pod                        │
  │             Hot-3 also runs ingest/transform                        │
  │                                                                     │
  │ Why 3 hot nodes:                                                    │
  │   - {hot_total:.0f} GB / {hot_storage_per_node} GB per node = {hot_total/hot_storage_per_node:.1f} (need {n_hot})            │
  │   - Distributes ingest load across 3 nodes                         │
  │   - Survives 1 node failure with 1 replica                         │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ WARM DATA NODES (x2)                                               │
  ├─────────────────────────────────────────────────────────────────────┤
  │ Role:       ES warm data (read-heavy, no active indexing)          │
  │ vCPU:       4                                                       │
  │ RAM:        16 GB                                                   │
  │   ES heap:  8 GB (-Xms8g -Xmx8g)                                  │
  │   OS cache: 6 GB                                                    │
  │   K3s/pods: 2 GB                                                    │
  │ Disk:       800 GB SSD (standard gp3, not NVMe required)           │
  │   Usable:   ~680 GB per node                                       │
  │   Holds:    90 days of data (0 replicas, force-merged)             │
  │ Network:    1 Gbps                                                  │
  │ IOPS:       1,500+ (lower requirement than hot)                    │""")

print(f"""  │                                                                     │
  │ Why 2 warm nodes:                                                   │
  │   - {warm_total:.0f} GB / 680 GB usable = {warm_total/680:.1f} (need {n_warm})                  │
  │   - Data is read-only, force-merged to 1 segment/shard             │
  │   - Warm-2 also co-hosts cold node role                            │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ COLD TIER (S3/MinIO-backed searchable snapshots)                   │
  ├─────────────────────────────────────────────────────────────────────┤
  │ Role:       ES frozen/cold — searchable snapshots from S3          │
  │ No dedicated nodes needed! Runs on warm-2 node                     │
  │ Storage:    S3-compatible bucket (MinIO on-prem or OCI Object St)  │
  │   Capacity: ~{cold_total:.0f} GB ({cold_total/1024:.1f} TB)                                    │
  │ RAM needed: ~1-2 GB for frozen cache on warm-2 node                │
  │ Local cache:100 GB SSD on warm-2 for frequently searched cold data │
  │                                                                     │
  │ How it works:                                                       │
  │   - ILM moves indices to frozen tier after {HOT_DAYS+WARM_DAYS} days               │
  │   - Data stored in S3 as searchable snapshots                      │
  │   - Queries fetch from S3 on-demand (slower but very cheap)        │
  │   - Local cache accelerates repeated queries                       │
  │                                                                     │
  │ If no S3 available:                                                 │
  │   Add 1 dedicated cold node:                                        │
  │   2 vCPU, 8 GB RAM, 2 TB HDD                                      │
  └─────────────────────────────────────────────────────────────────────┘
""")

# ============================================================
hr("5. TOTAL RESOURCE SUMMARY")
# ============================================================

masters_cpu = 3 * 2
masters_ram = 3 * 4
masters_disk = 3 * 50

hot_cpu = 3 * 8
hot_ram = 3 * 32
hot_disk = 3 * 400

warm_cpu = 2 * 4
warm_ram = 2 * 16
warm_disk = 2 * 800

total_cpu = masters_cpu + hot_cpu + warm_cpu
total_ram = masters_ram + hot_ram + warm_ram
total_disk_local = masters_disk + hot_disk + warm_disk

print(f"""
  ┌──────────────┬───────┬────────┬────────┬──────────────────────────┐
  │ Node Role    │ Count │ vCPU   │ RAM    │ Local Disk               │
  ├──────────────┼───────┼────────┼────────┼──────────────────────────┤
  │ K3s Master / │       │        │        │                          │
  │ ES Master    │   3   │  2 ea  │  4 GB  │  50 GB SSD ea            │
  │ (subtotal)   │       │  ({masters_cpu})   │ ({masters_ram} GB) │ ({masters_disk} GB)                  │
  ├──────────────┼───────┼────────┼────────┼──────────────────────────┤
  │ Hot Data     │   3   │  8 ea  │ 32 GB  │ 400 GB NVMe/SSD ea      │
  │ (subtotal)   │       │  ({hot_cpu})   │ ({hot_ram} GB) │ ({hot_disk} GB)                │
  ├──────────────┼───────┼────────┼────────┼──────────────────────────┤
  │ Warm Data    │   2   │  4 ea  │ 16 GB  │ 800 GB SSD ea           │
  │ (subtotal)   │       │  ({warm_cpu})    │ ({warm_ram} GB) │ ({warm_disk} GB)               │
  ├──────────────┼───────┼────────┼────────┼──────────────────────────┤
  │ Cold (S3)    │   0   │  n/a   │  n/a   │ {cold_total:.0f} GB in S3/MinIO     │
  ├──────────────┼───────┼────────┼────────┼──────────────────────────┤
  │ TOTAL        │   8   │  {total_cpu}    │ {total_ram} GB │ {total_disk_local/1000:.1f} TB local + {cold_total/1024:.1f} TB S3 │
  └──────────────┴───────┴────────┴────────┴──────────────────────────┘

  If deploying on OCI bare metal or VMs:
    Total vCPUs needed:    {total_cpu}
    Total RAM needed:      {total_ram} GB
    Total local SSD:       {total_disk_local/1000:.1f} TB
    Total object storage:  {cold_total/1024:.1f} TB (S3/OCI Object Storage)
""")

# ============================================================
hr("6. KUBERNETES WORKLOAD DISTRIBUTION")
# ============================================================

print("""
  ┌──────────────────────────────────────────────────────────────────┐
  │ Pod / StatefulSet Distribution                                    │
  ├───────────────────┬──────────┬────────┬──────────────────────────┤
  │ Component         │ Replicas │ RAM    │ Runs On                  │
  ├───────────────────┼──────────┼────────┼──────────────────────────┤
  │ ES Master         │    3     │ 1.5 GB │ master-1,2,3 (dedicated) │
  │ ES Hot Data       │    3     │  28 GB │ hot-1, hot-2, hot-3      │
  │ ES Warm Data      │    2     │  14 GB │ warm-1, warm-2           │
  │ Kibana            │    2     │  2 GB  │ hot-1, hot-3 (HA)        │
  │ Fleet Server      │    1     │  2 GB  │ hot-2                    │
  │ APM Server        │    1     │  1 GB  │ hot-2 (optional)         │
  │ MinIO (if on-prem)│    1     │  2 GB  │ warm-2 (or external S3)  │
  │ Monitoring        │    1     │  1 GB  │ master-1 (metricbeat)    │
  ├───────────────────┼──────────┼────────┼──────────────────────────┤
  │ TOTAL PODS        │   14     │        │                          │
  └───────────────────┴──────────┴────────┴──────────────────────────┘

  Node Affinity / Taints:
    masters:  taint=es-master:NoSchedule  (only ES master + k3s)
    hot-*:    label=elasticsearch.data=hot
    warm-*:   label=elasticsearch.data=warm
""")

# ============================================================
hr("7. ILM (INDEX LIFECYCLE MANAGEMENT) POLICY")
# ============================================================

print(f"""
  Policy: "watchwave-ilm"

  ┌──────────┬───────────────────────────────────────────────────────┐
  │ Phase    │ Actions                                               │
  ├──────────┼───────────────────────────────────────────────────────┤
  │ Hot      │ rollover: max_age=1d OR max_size=50GB                │
  │ (0-{HOT_DAYS}d)   │ priority: 100                                        │
  │          │ replicas: {REPLICA_HOT}                                            │
  │          │ shrink: no                                             │
  ├──────────┼───────────────────────────────────────────────────────┤
  │ Warm     │ trigger: min_age={HOT_DAYS}d                                    │
  │ ({HOT_DAYS}-{HOT_DAYS+WARM_DAYS}d)  │ replicas: {REPLICA_WARM}                                            │
  │          │ force_merge: max_num_segments=1                       │
  │          │ codec: best_compression (DEFLATE)                     │
  │          │ shrink: to 1 primary shard                            │
  │          │ priority: 50                                           │
  │          │ allocate: require.data=warm                            │
  ├──────────┼───────────────────────────────────────────────────────┤
  │ Cold     │ trigger: min_age={HOT_DAYS+WARM_DAYS}d                                  │
  │ ({HOT_DAYS+WARM_DAYS}-{RETENTION_DAYS}d) │ searchable_snapshot: full_copy to S3              │
  │          │ replicas: {REPLICA_COLD}                                            │
  │          │ priority: 0                                            │
  │          │ allocate: require.data=frozen                          │
  ├──────────┼───────────────────────────────────────────────────────┤
  │ Delete   │ trigger: min_age={RETENTION_DAYS}d                                  │
  │          │ delete index                                           │
  └──────────┴───────────────────────────────────────────────────────┘
""")

# ============================================================
hr("8. FLEET + ELASTIC AGENT INTEGRATIONS")
# ============================================================

print(f"""
  Fleet Server: Manages {AGENTS} Elastic Agents centrally

  Recommended Integrations (per agent):
  ┌─────────────────────────┬──────────┬───────────────────────────┐
  │ Integration             │ ~MB/day  │ Data Collected             │
  ├─────────────────────────┼──────────┼───────────────────────────┤
  │ Endpoint Security       │ 100-200  │ Process, file, network,   │
  │                         │          │ registry, malware events   │
  ├─────────────────────────┼──────────┼───────────────────────────┤
  │ System (auditd/syslog)  │  20-40   │ Auth logs, syslog,        │
  │                         │          │ system metrics             │
  ├─────────────────────────┼──────────┼───────────────────────────┤
  │ Windows Events          │  30-60   │ Security, PowerShell,     │
  │                         │          │ Sysmon (if installed)      │
  ├─────────────────────────┼──────────┼───────────────────────────┤
  │ Osquery (optional)      │   5-10   │ Scheduled host queries    │
  ├─────────────────────────┼──────────┼───────────────────────────┤
  │ Detection Engine alerts │  10-20   │ Triggered rule alerts     │
  ├─────────────────────────┼──────────┼───────────────────────────┤
  │ TOTAL per agent         │ 150-350  │                           │
  └─────────────────────────┴──────────┴───────────────────────────┘

  Agent Policies:
    - "Server Policy":    Endpoint + System + auditd (Linux servers)
    - "Workstation Policy": Endpoint + System + Windows Events
    - "Network Sensor":   Packet capture (if applicable)
""")

# ============================================================
hr("9. NETWORK & SECURITY REQUIREMENTS")
# ============================================================

print("""
  ┌──────────────────┬────────┬──────────────────────────────────────┐
  │ Traffic          │ Port   │ Description                          │
  ├──────────────────┼────────┼──────────────────────────────────────┤
  │ ES transport     │ 9300   │ Node-to-node (internal only)         │
  │ ES HTTPS API     │ 9200   │ Client access (Kibana, Fleet, API)   │
  │ Kibana           │ 5601   │ Web UI (expose via Ingress/LB)       │
  │ Fleet Server     │ 8220   │ Agent enrollment + check-in          │
  │ K3s API          │ 6443   │ Kubernetes API (internal)            │
  │ etcd             │ 2379   │ K3s embedded etcd (masters only)     │
  │ MinIO (if used)  │ 9000   │ S3-compatible object storage         │
  └──────────────────┴────────┴──────────────────────────────────────┘

  Bandwidth:
    - Ingest: 47 agents x ~350 MB/day = ~16 GB/day = ~1.5 Mbps sustained
    - Inter-node: ~2x ingest for replication = ~3 Mbps
    - Peak: 5-10 Mbps (during rollover/merge/recovery)
    - 1 Gbps NICs are MORE than sufficient

  Security:
    - ES 8.x has security enabled BY DEFAULT (TLS + RBAC)
    - Fleet enrollment tokens for agent auth
    - K3s network policy for pod isolation
    - Ingress with TLS termination for Kibana
""")

# ============================================================
hr("10. ESTIMATED COST (OCI / On-Prem VMs)")
# ============================================================

print(f"""
  ┌──────────────────────┬───────┬────────────────────────────────────┐
  │ Component            │ Qty   │ Monthly Cost (OCI estimate)        │
  ├──────────────────────┼───────┼────────────────────────────────────┤
  │ Master VMs           │       │                                    │
  │  VM.Standard.E4.Flex │   3   │ 2 OCPU, 4 GB = ~$25/mo ea = $75  │
  │  50 GB Block Vol     │   3   │ ~$3/mo ea = $9                    │
  ├──────────────────────┼───────┼────────────────────────────────────┤
  │ Hot Data VMs         │       │                                    │
  │  VM.Standard.E4.Flex │   3   │ 8 OCPU, 32 GB = ~$150/mo ea=$450 │
  │  400 GB Block Vol    │   3   │ ~$25/mo ea = $75                  │
  ├──────────────────────┼───────┼────────────────────────────────────┤
  │ Warm Data VMs        │       │                                    │
  │  VM.Standard.E4.Flex │   2   │ 4 OCPU, 16 GB = ~$75/mo ea = $150│
  │  800 GB Block Vol    │   2   │ ~$50/mo ea = $100                 │
  ├──────────────────────┼───────┼────────────────────────────────────┤
  │ Object Storage       │       │                                    │
  │  OCI Object Storage  │   -   │ {cold_total:.0f} GB @ $0.0255/GB = ~${cold_total*0.0255:.0f}/mo   │
  ├──────────────────────┼───────┼────────────────────────────────────┤
  │ Networking/LB        │   1   │ ~$20/mo                           │
  ├──────────────────────┼───────┼────────────────────────────────────┤
  │ TOTAL MONTHLY        │       │ ~$920-1,100/month                 │
  │ TOTAL ANNUAL         │       │ ~$11,000-13,200/year              │
  └──────────────────────┴───────┴────────────────────────────────────┘

  Cost comparison vs current:
    Current single-node VM:   ~$150-200/month (estimated)
    New HA cluster:           ~$920-1,100/month
    Premium for HA + ES8:     ~5-6x (but production-grade HA)

  Cost optimizations:
    - Use OCI Always Free tier for master nodes (2x AMD, 4 OCPU, 24GB)
    - Use preemptible/spot VMs for warm nodes (60-80% discount)
    - Use OCI Object Storage (10 GB free, then $0.0255/GB)
""")

# ============================================================
hr("11. DEPLOYMENT COMMANDS (K3s Quick Start)")
# ============================================================

print("""
  # Master-1 (init cluster)
  curl -sfL https://get.k3s.io | sh -s - server \\
    --cluster-init \\
    --tls-san <LOAD_BALANCER_IP> \\
    --disable traefik \\
    --node-taint es-master=true:NoSchedule

  # Master-2, Master-3 (join cluster)
  curl -sfL https://get.k3s.io | sh -s - server \\
    --server https://master-1:6443 \\
    --token <NODE_TOKEN> \\
    --node-taint es-master=true:NoSchedule

  # Hot workers
  curl -sfL https://get.k3s.io | sh -s - agent \\
    --server https://master-1:6443 \\
    --token <NODE_TOKEN> \\
    --node-label elasticsearch.data=hot

  # Warm workers
  curl -sfL https://get.k3s.io | sh -s - agent \\
    --server https://master-1:6443 \\
    --token <NODE_TOKEN> \\
    --node-label elasticsearch.data=warm

  # Deploy ES via ECK (Elastic Cloud on Kubernetes)
  kubectl apply -f https://download.elastic.co/downloads/eck/2.14.0/crds.yaml
  kubectl apply -f https://download.elastic.co/downloads/eck/2.14.0/operator.yaml
""")

# ============================================================
hr("12. FINAL SUMMARY")
# ============================================================

print(f"""
  ┌─────────────────────────────────────────────────────────────────┐
  │                    AT A GLANCE                                   │
  ├──────────────────────┬──────────────────────────────────────────┤
  │ Kubernetes           │ K3s (lightweight, HA, CNCF certified)   │
  │ ES Operator          │ ECK (Elastic Cloud on Kubernetes)       │
  │ Total Nodes          │ 8 (3 master + 3 hot + 2 warm)          │
  │ Total vCPUs          │ {total_cpu}                                       │
  │ Total RAM            │ {total_ram} GB                                    │
  │ Total Local Disk     │ {total_disk_local/1000:.1f} TB (SSD/NVMe)                    │
  │ Total Object Storage │ {cold_total/1024:.1f} TB (S3/MinIO/OCI Object)       │
  │ Avg EPS              │ {AVG_EPS} EPS                                   │
  │ Peak EPS             │ {PEAK_EPS} EPS                                   │
  │ Daily Ingestion      │ {DAILY_GB} GB/day → {peak_daily:.1f} GB/day (EOY)      │
  │ 1-Year Total Storage │ {total_storage/1024:.1f} TB (tiered)                      │
  │ Monthly Cost (OCI)   │ ~$920-1,100                              │
  │ Annual Cost          │ ~$11,000-13,200                          │
  │ HA / Fault Tolerance │ Survives 1 master + 1 data node failure │
  └──────────────────────┴──────────────────────────────────────────┘
""")
