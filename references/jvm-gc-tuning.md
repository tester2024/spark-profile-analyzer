# JVM GC Tuning Reference

## Aikar's Flags (G1GC)

The standard Aikar's flags are the most widely recommended JVM settings for Minecraft servers. They target G1GC and are tuned for low pause times with interactive workloads.

### Full Flag Set

```
-Xms10G -Xmx10G
-XX:+UseG1GC
-XX:+ParallelRefProcEnabled
-XX:MaxGCPauseMillis=200
-XX:+UnlockExperimentalVMOptions
-XX:+DisableExplicitGC
-XX:G1NewSizePercent=30
-XX:G1MaxNewSizePercent=40
-XX:G1HeapRegionSize=8M
-XX:G1RSetUpdatingPauseTimePercent=5
-XX:SurvivorRatio=32
-XX:MaxTenuringThreshold=1
-XX:G1MixedGCCountTarget=4
-XX:InitiatingHeapOccupancyPercent=15
-XX:G1MixedGCLiveThresholdPercent=90
-XX:G1OldCSetSetThresholdThreshold=JDK8:80,JDK11+:10
-XX:SurvivorRatio=32
-XX:PerTenureThreshold=1
-XX:G1OldCSetSetThresholdThreshold=10 (JDK 17+)
-XX:+AlwaysPreTouch
-XX:+UseLargePagesInMetaspace
-javaagent:spark.jar
```

### Flag Explanations

| Flag | Purpose | Details |
|------|---------|---------|
| `-Xms` / `-Xmx` | Min/max heap size | Must be equal to avoid heap resizing at runtime. Resizing causes GC pauses and memory fragmentation. |
| `-XX:+UseG1GC` | Enable G1 garbage collector | Region-based GC designed for low pause times. Best for heaps 4-32GB. |
| `-XX:+ParallelRefProcEnabled` | Parallel reference processing | Processes weak/soft/phantom references in parallel during GC. Reduces pause time significantly. |
| `-XX:MaxGCPauseMillis=200` | Target max pause time | G1GC tries to keep pauses under this. Setting to 200 balances throughput and latency. Too low causes excessive GC cycles. |
| `-XX:+UnlockExperimentalVMOptions` | Allow experimental flags | Required for some G1 tuning flags. |
| `-XX:+DisableExplicitGC` | Ignore System.gc() calls | Prevents plugins from triggering full GCs. Critical for Minecraft where some plugins call System.gc(). |
| `-XX:G1NewSizePercent=30` | Min young gen as % of heap | Forces young gen to be at least 30%. Prevents small young gens that cause frequent minor collections. Default is 5%, which is too small for MC. |
| `-XX:G1MaxNewSizePercent=40` | Max young gen as % of heap | Caps young gen at 40%. Prevents young gen from growing too large and causing long pause times. |
| `-XX:G1HeapRegionSize=8M` | Size of G1 regions | Larger regions reduce remset size and improve compaction. 8M for heaps 8-16GB, 16M for 16-32GB, 4M for <8GB. |
| `-XX:G1RSetUpdatingPauseTimePercent=5` | RSet update budget during pause | % of pause time allowed for remembered set updates. Lower = more concurrent work, less pause time. |
| `-XX:SurvivorRatio=32` | Eden vs survivor space ratio | Ratio of eden to survivor space. 32 means survivors are 1/32 of eden. Most MC objects die young, so large eden is good. |
| `-XX:MaxTenuringThreshold=1` | Max times object survives minor GC | Objects survive at most 1 minor GC before promoting to old gen. MC has mostly short-lived objects; quick promotion avoids copying overhead. |
| `-XX:G1MixedGCCountTarget=4` | Mixed GC collections per cycle | Number of mixed GCs per mixed collection cycle. Lower = more aggressive old gen cleanup per cycle. |
| `-XX:InitiatingHeapOccupancyPercent=15` | Trigger concurrent mark at 15% old gen | Starts concurrent marking when old gen is 15% occupied. Very aggressive to prevent old gen from filling up. Default is 45%, too late for MC. |
| `-XX:G1MixedGCLiveThresholdPercent=90` | Include regions up to 90% live | Mixed GCs will collect regions that are up to 90% garbage. Higher = more regions collected per mixed GC. |
| `-XX:+AlwaysPreTouch` | Touch all heap pages at startup | Commits all memory at JVM start instead of lazily. Prevents page faults during runtime that cause micro-stalls. Essential for MC. |

### Region Size Recommendations

| Heap Size | Region Size | Flag |
|-----------|-------------|------|
| < 4GB | 2M | `-XX:G1HeapRegionSize=2M` |
| 4-8GB | 4M | `-XX:G1HeapRegionSize=4M` |
| 8-16GB | 8M | `-XX:G1HeapRegionSize=8M` |
| 16-32GB | 16M | `-XX:G1HeapRegionSize=16M` |
| 32-64GB | 32M | `-XX:G1HeapRegionSize=32M` |

---

## ZGC (Z Garbage Collector)

ZGC is a concurrent garbage collector designed for sub-millisecond pauses. Available since JDK 11 (production-ready in JDK 15+), and significantly improved in JDK 17+ and JDK 21+.

### Recommended Flags

```
-Xms10G -Xmx10G
-XX:+UseZGC
-XX:+AlwaysPreTouch
-XX:+ParallelRefProcEnabled
-XX:+DisableExplicitGC
-XX:SoftMaxHeapSize=8G
-XX:ZAllocationSpikeTolerance=2
```

### ZGC-Specific Flags

| Flag | Purpose | Details |
|------|---------|---------|
| `-XX:+UseZGC` | Enable ZGC | Concurrent GC with sub-millisecond STW pauses. |
| `-XX:SoftMaxHeapSize` | Soft heap limit | ZGC will try to keep heap below this while still allowing it up to -Xmx under pressure. Set to ~80% of -Xmx. JDK 13+. |
| `-XX:ZAllocationSpikeTolerance` | Allocation spike tolerance | How much ZGC pre-allocates for spikes. Higher = more memory used but fewer allocation stalls. Default 1, use 2-3 for MC. |
| `-XX:ZFragmentationLimit` | Acceptable fragmentation | (JDK 21+) Max acceptable heap fragmentation percentage. Default 5%. |
| `-XX:+ZGenerational` | Enable Generational ZGC | (JDK 21+) Separates young/old gen for ZGC. Significantly better performance. Always use on JDK 21+. |

### ZGC Cycles vs Pauses (Critical Distinction)

| Concept | Thread-blocking? | Duration | What it means |
|---------|-------------------|----------|---------------|
| **ZGC Cycle** | No - concurrent | 100ms-10s+ | Normal concurrent marking/relocation. Does NOT cause lag. |
| **ZGC Pause** | Yes - STW | 0.1-1ms | Brief safety point for root scanning. Negligible impact. |
| **ZGC Allocation Stall** | Yes - STW | Variable | Thread runs out of memory and waits for GC. Bad sign. |

**Key insight**: When analyzing Spark data, ZGC "cycles" shown in GC frequency are NOT STW pauses. Only ZGC "Pauses" count toward lag. If you see many ZGC cycles but low pause time, the GC is working fine.

### When to Choose ZGC vs G1GC

| Factor | G1GC Preferred | ZGC Preferred |
|--------|----------------|---------------|
| Heap size | 4-16GB | 16GB+ |
| JDK version | Any (8+) | 17+ (21+ for generational) |
| Player count | < 100 | 100+ |
| Server type | Survival, small community | Large network, modded |
| Tolerance for pauses | Can handle 50-200ms pauses | Need < 1ms pauses |
| Memory budget | Tight (4-8GB) | Generous (16GB+) |
| CPU cores | 2-4 | 4+ (ZGC needs more concurrent threads) |
| Workload type | Mostly young-gen churn | Heavy old-gen pressure |

### ZGC Tuning Guidelines

1. **Heap size**: Allocate 25-50% more than G1GC would need. ZGC trades memory for concurrency.
2. **CPU**: ZGC concurrent threads use CPU during cycles. Ensure 4+ cores available.
3. **JDK 21+ with Generational ZGC**: Always use `-XX:+ZGenerational` on JDK 21+. It separates young/old gen handling and dramatically reduces allocation stalls.
4. **Allocation stalls**: If Spark shows allocation stalls, increase heap or increase `ZAllocationSpikeTolerance`.
5. **SoftMaxHeapSize**: Set to ~80% of Xmx. Allows ZGC to be more aggressive about returning memory while having headroom.

---

## Common JVM Flags Reference

| Flag | Purpose | Recommended | Impact |
|------|---------|-------------|--------|
| `-Xms` | Initial heap size | Same as Xmx | Avoids resize pauses |
| `-Xmx` | Max heap size | See sizing below | Main memory allocation |
| `-XX:+AlwaysPreTouch` | Pre-commit memory | Always | Eliminates page fault stalls |
| `-XX:+ParallelRefProcEnabled` | Parallel ref processing | Always | Reduces GC pause 10-30% |
| `-XX:+DisableExplicitGC` | Ignore System.gc() | Always | Prevents plugin-triggered full GCs |
| `-XX:+UseG1GC` | Use G1 collector | Default for most MC | Region-based low-pause GC |
| `-XX:+UseZGC` | Use ZGC collector | For large/heavy servers | Sub-ms pauses, needs JDK 15+ |
| `-XX:MaxGCPauseMillis` | GC pause target | 200 (G1) | Lower = more frequent GC, higher = longer pauses |
| `-XX:+UseLargePagesInMetaspace` | Large pages for metaspace | If OS configured | Reduces TLB misses |
| `-XX:+UseCompressedOops` | Compressed object pointers | Auto (heap < 32GB) | Saves ~40% heap memory. DO NOT disable. |
| `-Dpaper.playerconnection.keepalive=60` | KeepAlive timeout | 60 | Prevents false timeouts |
| `-XX:+UseStringDeduplication` | String dedup | Optional for G1 | Reduces memory for duplicate strings |
| `-XX:InitialSurvivorRatio` | Survivor space ratio | 32 (Aikar's) | More eden = fewer minor GCs |
| `-XX:InitiatingHeapOccupancyPercent` | Concurrent mark trigger | 15 (Aikar's) | Prevents old gen overflow |

---

## Memory Sizing Recommendations

### Per-Player RAM Estimates

| Server Type | RAM/Player | Total for 50 players | Total for 100 players |
|-------------|------------|---------------------|----------------------|
| Vanilla Survival | 50-100MB | 4-6GB | 8-12GB |
| Paper Survival | 40-80MB | 4-6GB | 8-12GB |
| modded (light) | 150-250MB | 8-10GB | 16-24GB |
| modded (heavy) | 250-500MB | 12-16GB | 24-48GB |
| Minigames | 30-50MB | 4GB | 6-8GB |
| Anarchy/claimless | 80-150MB | 6-8GB | 12-16GB |

### Base RAM Allocation

| Component | RAM |
|-----------|-----|
| OS + system | 1-2GB |
| JVM overhead (non-heap) | 500MB-1GB |
| Minecraft base (no players) | 1-2GB |
| Each world loaded | 500MB-1GB |
| Each heavily-modded dimension | 1-2GB extra |

### Total Formula

```
Total RAM = (Base overhead ~2-3GB) + (Players × per-player RAM) + (Worlds × 500MB) + 20% buffer
```

**Important**: Never allocate ALL system RAM to the JVM. Leave at least 2GB for OS, 1GB+ for page cache, and room for off-heap allocations.

---

## Bad Flags to Avoid

| Flag | Why it's bad | What to do instead |
|------|-------------|-------------------|
| `-XX:+UseParNewGC` | Outdated, removed in JDK 11+ | Use G1GC |
| `-XX:+UseConcMarkSweepGC` | Removed in JDK 14+ | Use G1GC or ZGC |
| `-XX:+UseSerialGC` | Single-threaded, terrible for MC | Use G1GC |
| `-XX:+AggressiveOpts` | Unstable optimizations, may crash | Remove it |
| `-XX:+UseLargePages` | Requires OS config, crashes if misconfigured | Use LargePagesInMetaspace |
| `-Xmn` / `-XX:NewSize` | Overrides G1 adaptive sizing | Use G1NewSizePercent |
| `-XX:SurvivorRatio=8` | Default too small for MC | Use 32 (Aikar's) |
| `-XX:MaxTenuringThreshold=15` | Default too high for MC | Use 1 (Aikar's) |
| `-XX:+UseStringDeduplication` with ZGC | Not supported/needed | Remove for ZGC |
| `-XX:ParallelGCThreads` with wrong value | Too low = slow GC, too high = CPU waste | Leave default (auto-detected) |
| `-Xms != -Xmx` | Causes heap resizing pauses | Always set equal |
| `> 32GB heap without compressed oops` | Loses ~40% effective memory cap | Stay ≤ 30-31GB or jump to 40GB+ |

---

## GC Pause Time Targets and TPS Impact

| Pause Duration | TPS Impact | Player Impact |
|---------------|------------|---------------|
| < 10ms | None (within 50ms tick) | Imperceptible |
| 10-50ms | Minor (1-2 tick delay) | Barely noticeable |
| 50-100ms | Moderate (2-4 tick delay) | Noticeable rubber-banding |
| 100-200ms | Significant (5-10 tick delay) | Blocks breaking, desync |
| 200-500ms | Severe (10-25 tick delay) | Players get kicked |
| > 500ms | Critical (25+ tick delay) | Timeout kicks, data loss |

A single 50ms tick must complete in 50ms. A GC pause of 100ms causes at least 2 missed ticks (100ms / 50ms), resulting in TPS drop from 20 to ~16.7 during that window.

---

## JDK Version Recommendations

| Version | Status | Notes |
|---------|--------|-------|
| JDK 8 | EOL | Use only for 1.8.8-1.12.2. Missing key G1 improvements. |
| JDK 11 | EOL | Better G1, basic ZGC. |
| JDK 17 | LTS | Recommended minimum. Good G1 + ZGC. |
| JDK 21 | LTS | Best current option. Generational ZGC, improved G1. |
| JDK 23+ | Latest | Cutting-edge features. Use for ZGC generational improvements. |