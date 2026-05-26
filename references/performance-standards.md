# Performance Threshold Reference

Concrete thresholds for evaluating Minecraft server health from Spark profiler data and runtime metrics.

---

## TPS (Ticks Per Second)

| Rating | TPS | Description |
|--------|-----|-------------|
| GOOD | >= 19.5 | Server running smoothly. Players experience no lag. |
| WARNING | 15.0 - 19.5 | Noticeable lag. Block breaking delays, rubber-banding. Gameplay degraded. |
| CRITICAL | < 15.0 | Severe lag. Commands delayed, entities frozen, combat broken. Players leaving. |

**Context**: Target TPS is 20. A TPS of 19.5 means the server is losing ~1 tick every 2 seconds. At TPS 15, the server is running 25% slower than normal. Below 10 TPS, the server is effectively unplayable.

**Spark metric**: `tps` in tick data. Calculated from rolling average of recent tick durations.

---

## MSPT (Milliseconds Per Tick)

| Rating | MSPT | P95 Threshold | Max Threshold | Description |
|--------|------|--------------|---------------|-------------|
| GOOD | < 30ms | < 40ms | < 50ms | Server comfortably within 50ms budget. Good headroom. |
| WARNING | 30-45ms | 40-80ms | 50-150ms | Server using most of tick budget. Occasional delays. |
| CRITICAL | > 45ms | > 80ms | > 150ms | Server cannot keep up. Sustained lag, missed ticks. |

**Explanation**: Each tick must complete within 50ms (1000ms / 20 TPS). MSPT of 50ms = exactly 20 TPS. MSPT of 100ms = 10 TPS.

**P95 (95th percentile)**: 5% of ticks exceed this. Occasional spikes above 50ms are normal; sustained P95 > 50ms indicates systemic issues.

**Max**: The worst tick in the measurement window. A max of 200ms+ means at least one tick caused 4+ missed ticks.

### MSPT Breakdown Targets

| Component | Target MSPT | Warning | Critical |
|-----------|------------|---------|----------|
| Entity ticking | < 10ms | 10-20ms | > 20ms |
| Chunk loading | < 5ms | 5-15ms | > 15ms |
| Plugin scheduler | < 3ms | 3-10ms | > 10ms |
| Network processing | < 5ms | 5-10ms | > 10ms |
| GC pauses | < 10ms | 10-50ms | > 50ms |

---

## GC Frequency

| Rating | G1GC Young Gen | G1GC Old Gen | ZGC Cycles | ZGC Pauses |
|--------|---------------|-------------|------------|------------|
| GOOD | < 1/min (normal: every 1-2s is fine for young gen) | < 1/5min | N/A (cycles are concurrent) | < 1/min |
| WARNING | 1-5/min (frequent but not crisis) | 1-5/5min | See below | 1-5/min |
| CRITICAL | > 5/min sustained | > 1/min (full GC) | Allocation stalls > 0 | > 5/min |

**Important clarification for G1GC**:
- **Young gen collections** every 1-2 seconds are NORMAL. Young gen is designed for frequent, short collections.
- The concern is when young gen collections take > 50ms each, OR when they trigger excessively due to small heap.
- **Mixed/old gen collections** should be infrequent. Frequent old gen collections indicate memory pressure.

**ZGC-specific notes**:
- ZGC **cycles** run concurrently and do NOT block the application. High cycle frequency is not directly a problem.
- Only ZGC **pauses** (STW) affect TPS. These are normally sub-millisecond.
- **ZGC allocation stalls** are always bad. They mean a thread needed memory and had to wait for GC.

---

## GC Pause Duration (STW Only)

| Rating | G1GC Pause | ZGC Pause | Impact on TPS |
|--------|-----------|-----------|---------------|
| GOOD | < 50ms | < 1ms | No perceptible lag |
| WARNING | 50-200ms | 1-5ms | Some tick delays, mild rubber-banding |
| CRITICAL | > 200ms | > 5ms | Missed ticks, players kicked on extreme pauses |

**Key distinction**: These thresholds apply ONLY to Stop-The-World pauses. Concurrent GC work (ZGC cycles, G1 concurrent marking) does not block threads and is measured separately.

### ZGC Cycle vs Pause (Critical)

| Metric | Is STW? | Threshold | Lag Impact |
|--------|---------|-----------|------------|
| ZGC Minor/Regular Cycle | NO (concurrent) | Not a lag concern | None |
| ZGC Major/Full Cycle | NO (concurrent) | High frequency indicates memory pressure | Indirect (CPU contention) |
| ZGC Pause | YES (STW) | < 1ms GOOD, 1-5ms WARNING, > 5ms CRITICAL | Direct |
| ZGC Allocation Stall | YES (per-thread STW) | 0 = GOOD, any = investigate | Direct |

---

## CPU Usage

| Rating | Process CPU% | System CPU% | Description |
|--------|-------------|-------------|-------------|
| GOOD | < 60% | < 50% | Healthy headroom for GC, OS, and spikes |
| WARNING | 60-80% | 50-75% | Limited headroom. Spikes may cause lag. |
| CRITICAL | > 80% | > 75% | No headroom. Consistent lag under load. |

**Process CPU%**: CPU used by the JVM process across all threads. On a 4-core system, 100% = 1 core fully used, 400% = all cores maxed.

**System CPU%**: Total system CPU including other processes. High system CPU with lower process CPU = another process competing for resources.

### CPU Per Core (for Folia/multi-threaded)

| Rating | Per-Core Usage | Description |
|--------|---------------|-------------|
| GOOD | < 70% | Core has headroom |
| WARNING | 70-90% | Core near capacity |
| CRITICAL | > 90% | Core saturated, queuing work |

### CPU Steal (Virtualized Hosts)

| Rating | CPU Steal % | Description |
|--------|------------|-------------|
| GOOD | < 2% | Host has resources available |
| WARNING | 2-10% | Host overcommitted, occasional steals |
| CRITICAL | > 10% | Host severely overcommitted. Switch providers. |

CPU steal means the hypervisor is taking CPU time away from your VM for other tenants. This cannot be fixed by JVM tuning.

---

## Memory Usage

| Rating | Heap Utilization | Description |
|--------|-----------------|-------------|
| GOOD | < 70% | Plenty of room for GC to work |
| WARNING | 70-85% | GC working harder. More frequent collections. |
| CRITICAL | > 85% | GC thrashing. Risk of OOM. Full GCs imminent. |

### OOM Warning Signs

| Sign | What it means |
|------|---------------|
| Old gen > 90% sustained | Objects not being collected. OOM imminent. |
| Full GC frequency increasing | GC can't keep up. |
| Allocation failures/stalls | Threads blocked waiting for memory. |
| `java.lang.OutOfMemoryError` in logs | OOM has occurred. Increase heap or fix leak. |
| Rapid heap growth after startup | Possible memory leak in plugin. |

### Memory by Component (Typical)

| Component | % of Heap | Notes |
|-----------|----------|-------|
| Entity data | 10-30% | Largest consumer on populated servers |
| Chunk data | 15-35% | Loaded chunks in player view distance |
| Player data | 5-15% | Per-player state, inventory |
| Plugin data | 5-25% | Varies wildly by plugin |
| JVM overhead | 5-10% | Internal JVM structures |

---

## Entity Counts

| Rating | Total per World | Active per World | Notes |
|--------|----------------|-----------------|-------|
| GOOD | < 1000 | < 300 | Healthy entity load |
| WARNING | 1000-3000 | 300-800 | Significant entity processing. Watch MSPT. |
| CRITICAL | > 3000 | > 800 | Entity lag likely. Reduce spawn limits or view distance. |

### Entity Types - Warning Thresholds

| Entity Type | Warning | Critical | Why |
|-------------|---------|----------|-----|
| Item (dropped) | > 200 per world | > 500 | Items tick every tick. Merge radius is critical. |
| XP Orb | > 100 per world | > 300 | XP orbs are very CPU-intensive. |
| Villager | > 50 per world | > 150 | Villagers have complex AI. |
| Minecart | > 30 per world | > 100 | Minecarts with hopper are especially heavy. |
| Arrow | > 100 per world | > 300 | Arrows tick until despawn. |
| Falling block | > 50 | > 200 | Sand/gravel physics. |
| Any single type | > 500 per world | > 1000 | Unbalanced entity distribution indicates a farm or misconfiguration. |

---

## Chunk Counts

| Rating | Loaded Chunks | Per Player | Notes |
|--------|--------------|-----------|-------|
| GOOD | < 3000 | < 150 | Normal for small/medium servers |
| WARNING | 3000-8000 | 150-300 | High chunk count. Watch memory. |
| CRITICAL | > 8000 | > 300 | Excessive. Reduce view-distance. |

### Chunk Count Estimation

```
Chunks per player ≈ (2 × view-distance + 1)² - (2 × simulation-distance + 1)²  [non-ticking] +
                    (2 × simulation-distance + 1)²  [ticking]
Total ≈ (2 × view-distance + 1)² × player_count (worst case, no overlap)
```

| View Distance | Chunks per Player | At 50 Players | At 100 Players |
|--------------|-----------------|---------------|----------------|
| 4 | 81 | 4,050 | 8,100 |
| 5 | 121 | 6,050 | 12,100 |
| 6 | 169 | 8,450 | 16,900 |
| 7 | 225 | 11,250 | 22,500 |
| 8 | 289 | 14,450 | 28,900 |

---

## Player Count Capacities

| Server Type | RAM | Typical Max Players | TPS Expectation |
|-------------|-----|--------------------|-----------------|
| Paper, survival | 8GB | 30-50 | 20 TPS achievable |
| Paper, survival | 16GB | 50-100 | 20 TPS achievable |
| Paper, survival | 32GB | 100-200 | 19-20 TPS with good config |
| Folia, survival | 32GB | 200-400+ | 20 TPS (parallelized) |
| Paper, minigames | 8GB | 50-80 | 20 TPS (lighter per player) |
| Paper, modded | 16GB | 20-40 | 18-20 TPS |

---

## Thread Health (Spark Thread View)

| Rating | Sleep % | Description |
|--------|---------|-------------|
| HEALTHY | > 50% | Thread has ample time between tasks. Server is not overloaded. |
| MODERATE | 20-50% | Thread is busy but keeping up. Monitor for degradation. |
| OVERLOADED | < 20% | Thread is saturated. Work is queuing. Lag imminent or present. |
| SATURATED | ~0% | Thread never sleeps. Critical - cannot process all work. |

### Thread Types on Minecraft Servers

| Thread | Healthy Sleep % | Warning | Overloaded | What to check |
|--------|----------------|---------|------------|---------------|
| Server Main Thread | > 40% | 20-40% | < 20% | Entity count, plugin scheduling, chunk loading |
| Netty I/O threads | > 60% | 30-60% | < 30% | Connection flood, packet processing |
| Chunk I/O threads | > 50% | 20-50% | < 20% | Chunk generation rate, disk I/O speed |
| GC threads | > 70% | 40-70% | < 40% | Memory pressure, allocation rate |
| Scheduled executor | > 50% | 20-50% | < 20% | Plugin async tasks |

---

## Spark-Specific Thresholds

### avg_frequency Interpretation

| avg_frequency | Meaning | Action |
|-------------|---------|--------|
| Very high (> 100/s) | Hot method, called frequently | Optimize if total time is also high |
| High (10-100/s) | Actively used method | Check if time per call is reasonable |
| Medium (1-10/s) | Normal usage | Usually not a concern |
| Low (< 1/s) | Infrequent calls | Rarely a performance concern |

### avg_time Interpretation

| avg_time per call | Meaning | Action |
|------------------|---------|--------|
| > 50ms | Extremely slow for MC (1+ ticks) | Critical - investigate immediately |
| 10-50ms | Slow (significant portion of tick) | Investigate - may be acceptable for async |
| 1-10ms | Moderate | Check frequency × time = total impact |
| < 1ms | Fast | Usually not a concern unless called millions of times |
| < 0.01ms | Very fast | Not a concern |

### Total Time Contribution

| Total % of tick | Rating | Action |
|----------------|--------|--------|
| > 20% | CRITICAL | This single method consumes 20%+ of tick budget |
| 10-20% | WARNING | Significant contributor. Investigate. |
| 5-10% | MODERATE | Worth monitoring. |
| < 5% | OK | Acceptable for most methods. |

---

## Quick Diagnosis Table

| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| TPS 15-19, MSPT 30-50 | Moderate entity/chunk load | entity-activation-range, spawn-limits, view-distance |
| TPS < 15, MSPT > 50 | Severe overload | Check Spark tick thread view, reduce all limits |
| TPS drops with players joining | Connection handling or chunk loading | max-joins-per-tick, view-distance |
| Periodic TPS dips (every X seconds) | Scheduled task or auto-save | Check plugin schedulers, auto-save interval |
| TPS fine but GC pauses high | Memory pressure | Increase heap or reduce allocation rate |
| System CPU high, process CPU normal | Another process | Check `top`/`htop` for non-Java processes |
| CPU steal > 5% | Bad host | Cannot fix - change hosting provider |
| Memory > 85% used | Small heap or leak | Increase heap or investigate plugin memory use |