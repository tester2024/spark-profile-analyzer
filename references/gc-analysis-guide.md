# Deep GC Analysis Patterns

Guide for interpreting garbage collection data from Spark profiler output and making tuning decisions.

---

## Reading Spark GC Data

Spark exposes GC information through its profiling data. Key fields:

| Field | What it shows | Unit |
|-------|--------------|------|
| `avg_frequency` | How often a GC event occurs | events/sec |
| `avg_time` | Average duration of each event | ms |
| `total_time` | Cumulative time spent in GC | ms |
| `gc_type` | Type of collection (Young/Mixed/Old for G1, Cycle/Pause for ZGC) | label |

### What to Look For

1. **avg_time for STW pauses** - This is the direct lag impact. If avg_time for a STW event is > 50ms, it's causing noticeable lag.
2. **avg_frequency** - How often GC runs. Frequent STW pauses add up.
3. **total_time** - What % of profiling time was spent in GC. > 5% is concerning.
4. **GC type breakdown** - Which generation/phase is consuming time.

---

## ZGC Analysis

### Understanding ZGC Cycles vs Pauses

**This is the most common source of misanalysis.** ZGC performs most work concurrently. Understanding the difference is critical.

| Event | STW? | Duration | Frequency | Lag Impact |
|-------|------|----------|-----------|------------|
| Minor Collection Cycle | NO | 10ms-5s+ | Every few seconds | **None** - runs concurrently with application |
| Major Collection Cycle | NO | 1-30s+ | Every few minutes under pressure | **None** - concurrent. High frequency = memory pressure warning |
| Pause (Minor) | YES | 0.1-0.5ms | Every cycle start | **Negligible** - sub-millisecond |
| Pause (Major) | YES | 0.1-1ms | Rare | **Negligible** |
| Allocation Stall | YES | Variable (until GC frees memory) | Should be 0 | **Critical** - thread blocked |

### When ZGC Minor Pauses Indicate Issues

| Observation | Meaning | Action |
|-------------|---------|--------|
| ZGC Pause avg_time > 1ms | Possible issue with root scanning | Check if JDK 21+ for generational ZGC |
| ZGC Pause avg_time > 5ms | Serious - ZGC pauses should be sub-ms | Possible JVM bug or extremely large heap. Update JDK. |
| ZGC Pauses increasing over time | Memory pressure causing longer root scans | Consider increasing heap or reducing allocation rate |
| ZGC Allocation Stalls > 0 | Critical - threads blocked waiting for memory | Increase heap size or ZAllocationSpikeTolerance |

### When ZGC Major Cycles Are Concerning

| Observation | Meaning | Action |
|-------------|---------|--------|
| Major cycles every few minutes | Normal behavior | None |
| Major cycles every 30s | High old-gen pressure | Check for memory leaks, increase heap |
| Major cycles every 10s | Severe memory pressure | Increase heap 50-100%, investigate leaks |
| Cycles not completing (stuck) | Heap nearly full, GC can't keep up | Immediate: increase heap. Long-term: fix allocation pattern. |
| Cycles using > 20% CPU | GC competing with app for CPU | More cores or reduce allocation rate |

### Generational ZGC (JDK 21+)

With `-XX:+ZGenerational`, ZGC separates young and old generations:
- Young objects collected in minor cycles (fast, frequent)
- Old objects collected in major cycles (less frequent)
- Dramatically reduces allocation stalls
- **Always use on JDK 21+**

---

## G1GC Analysis

### Understanding G1 Collections

| Event | STW? | Typical Duration | Typical Frequency | Purpose |
|-------|------|-----------------|-------------------|---------|
| Young Gen Collection | YES | 10-100ms | Every 1-5 seconds | Collects short-lived objects in young gen |
| Mixed Collection | YES | 20-150ms | During mixed GC phase | Collects young gen + some old gen regions |
| Concurrent Mark | NO | 100ms-1s | Triggered at IHOP | Marks live objects in old gen |
| Full GC | YES | 500ms-10s+ | Should be near 0 | Collects entire heap. **Always a problem.** |

### When G1 Pause Times Are Problematic

| Pause Type | Good | Warning | Critical | Action |
|-----------|------|---------|----------|--------|
| Young Gen | < 50ms | 50-100ms | > 100ms | Check young gen size, region size, ParallelGCThreads |
| Mixed | < 100ms | 100-200ms | > 200ms | Check InitiatingHeapOccupancyPercent, MixedGCCountTarget |
| Full GC | 0 | Any occurrence | > 0 | Investigate immediately - indicates heap too small or leak |

### G1 Young Gen Collection Frequency

| Frequency | Meaning | Action |
|-----------|---------|--------|
| 1-4 seconds | Normal for Aikar's flags | None |
| < 1 second | Young gen too small or too much allocation | Reduce allocation rate or increase G1NewSizePercent |
| > 10 seconds | Very large young gen or very low allocation | Could reduce G1MaxNewSizePercent |

### Identifying G1 Evacuation Failures

Evacuation failure = G1 couldn't move objects because there was no free space. This dramatically increases pause time.

| Sign | What it means |
|------|-------------|
| "Evacuation Failure" in GC logs | Young gen or old gen too full |
| Pause time > 5x normal | G1 doing extra work to handle failure |
| To-space exhausted | Need more heap or different region sizing |

---

## GC Allocation Rate Correlation

### The Fundamental Relationship

```
Allocation Rate → Young Gen Fill Speed → Young GC Frequency → Pause Frequency → Lag
```

High allocation rate directly causes frequent young gen collections. Each collection is a STW pause.

### Allocation Rate Benchmarks

| Allocation Rate | G1 Young GC Frequency | Impact | Typical Cause |
|----------------|----------------------|--------|---------------|
| < 100 MB/s | Every 5-10s | Minimal | Normal survival server |
| 100-500 MB/s | Every 1-5s | Moderate | Active server, some farms |
| 500 MB/s - 1 GB/s | Every 0.5-2s | Significant | Busy server, many entities |
| > 1 GB/s | Multiple per second | High | Entity farms, plugin churn, memory leak |

### What Drives Allocation Rate

| Source | Typical Rate | How to Reduce |
|--------|-------------|---------------|
| Entity ticking | High | Reduce entity count, activation range |
| Chunk generation | Very high (burst) | Pre-generate world, reduce view-distance |
| Packet processing | Medium | Optimize packet handlers |
| Plugin object churn | Varies | Profile plugin allocation hotspots |
| NBT serialization | Medium | Reduce NBT ops per tick |
| String operations | Low-Medium | Use StringBuilder, avoid concatenation in loops |

---

## Memory Pressure Patterns

### Pattern 1: Growing Old Gen → Full GC → OOM

```
Timeline:
[Normal] Old gen slowly growing → 60% → 70% → 80%
[Warning] G1 mixed collections increasing → 85% → 90%
[Critical] Full GC triggered → pause 1-10 seconds → frees some space
[Terminal] Full GC cannot free enough → OOM
```

**Diagnosis**: Objects that should be short-lived are being promoted to old gen. Either the young gen is too small, or there's a genuine memory leak.

**Action**:
1. Check if MaxTenuringThreshold=1 is set (Aikar's default). If objects survive 1 young GC, they go to old gen.
2. Check for memory leaks: take heap dumps and compare old gen contents over time.
3. Increase heap size as a stopgap.

### Pattern 2: Allocation Rate Spike → GC Thrashing

```
Timeline:
[Normal] Allocation at 200 MB/s → Young GC every 3s
[Event] Player joins / chunk load burst → Allocation spikes to 2 GB/s
[Lag] Young GC every 200ms → 10 pauses per second → TPS drops
[Recovery] Spike ends → returns to normal
```

**Diagnosis**: Burst allocations overwhelm young gen capacity.

**Action**:
1. Increase G1NewSizePercent to give larger young gen (absorbs spikes)
2. Reduce max-joins-per-tick (Paper) to smooth out join bursts
3. Pre-generate worlds to eliminate chunk generation allocation

### Pattern 3: Stable High Usage → Marginal GC

```
Timeline:
[Stable] Old gen at 75% → Mixed GCs every 30s → Pauses 80ms
[Load increases] More players → Old gen rises to 85%
[Thrashing] Mixed GCs every 10s → Pauses 150ms → CPU 50%+ for GC
```

**Diagnosis**: Server is at the edge of what its heap can handle.

**Action**:
1. Increase heap 25-50%
2. Reduce entity count and chunk loading
3. Consider switching to ZGC if heap > 16GB

---

## GC Impact on TPS

### How GC Pauses Translate to MSPT Spikes

```
A single G1 young gen pause of 80ms during a tick:
- Tick budget: 50ms
- GC takes: 80ms (during or overlapping with tick)
- Effective MSPT for that tick: 50ms (work) + 80ms (GC) = 130ms worst case
- TPS impact: 1000/130 = ~7.7 TPS for that single tick
- Rolling TPS: depends on averaging window
```

### GC to TPS Correlation Table

| Avg GC Pause | GCs per 10s | Total GC Time/10s | Effective TPS Loss |
|-------------|-------------|-------------------|-------------------|
| 20ms | 5 | 100ms | ~0.2 TPS (negligible) |
| 50ms | 5 | 250ms | ~0.5 TPS (minor) |
| 100ms | 5 | 500ms | ~1 TPS (noticeable) |
| 100ms | 10 | 1000ms | ~2 TPS (significant) |
| 200ms | 5 | 1000ms | ~2 TPS (problematic) |
| 200ms | 10 | 2000ms | ~4 TPS (severe) |

### The Multiplicative Effect

When GC pauses overlap with high tick work:
- Normal tick: 30ms work + 10ms margin = 40ms MSPT (fine)
- GC during tick: 30ms work + 80ms GC = 110ms MSPT (lag spike)
- Player impact: block ghosting, rubber-banding, combat desync

---

## Interpreting avg_frequency and avg_time from Spark

### Interpretation Matrix

| avg_frequency | avg_time | Diagnosis | Action |
|--------------|---------|-----------|--------|
| High (> 100/s) | Low (< 1ms) | Normal young gen GC | No action unless total time is high |
| High | High (> 50ms) | Frequent long pauses | **Critical** - GC is causing significant lag |
| Low (< 1/s) | Very high (> 500ms) | Full GC or major collection | **Critical** - investigate memory pressure |
| Medium (1-10/s) | Medium (10-50ms) | Moderate GC pressure | Monitor, consider heap increase |
| Low | Low | Normal background GC | No action needed |

### Total Time Percentage

| % of Profile Time in GC | Rating | Meaning |
|------------------------|--------|---------|
| < 1% | GOOD | GC overhead negligible |
| 1-3% | OK | Normal for actively used server |
| 3-5% | WARNING | GC consuming significant resources |
| 5-10% | CONCERNING | GC overhead impacting server performance |
| > 10% | CRITICAL | GC is a major bottleneck |

---

## GC Tuning Decision Tree

```
Is GC causing lag? (STW pauses > 50ms or > 5% of time)
│
├── NO → Don't tune GC. Focus on game logic / entities / plugins.
│
└── YES → What GC algorithm?
    │
    ├── G1GC
    │   ├── Are Full GCs occurring?
    │   │   ├── YES → Heap too small. Increase Xmx 50%.
    │   │   └── NO → Are young gen pauses > 100ms?
    │   │       ├── YES → Young gen too large or too many objects. Reduce G1MaxNewSizePercent.
    │   │       └── NO → Are mixed GC pauses > 150ms?
    │   │           ├── YES → Old gen filling fast. Reduce IHOP, increase heap.
    │   │           └── NO → Pauses < 100ms but still lag?
    │   │               └── Frequency too high → Increase heap or reduce allocation rate.
    │
    └── ZGC
        ├── Are there allocation stalls?
        │   ├── YES → Increase heap or ZAllocationSpikeTolerance. Use generational ZGC (JDK 21+).
        │   └── NO → Are pauses > 5ms?
        │       ├── YES → Possible JDK bug. Update JDK. Check heap region count.
        │       └── NO → Are cycles very frequent (> 1/s)?
        │           ├── YES → High allocation rate. Increase heap, reduce entity/chunk load.
        │           └── NO → GC is fine. Lag is from game logic, not GC.
```

### Heap Size Decision

| Current Heap | Observed Old Gen % | Recommendation |
|-------------|-------------------|----------------|
| < 8GB | > 70% | Increase to 10-12GB |
| 8-16GB | > 60% | Increase to 16-20GB |
| 16-24GB | > 50% | Increase to 24-32GB or switch to ZGC |
| 24-32GB | > 50% | Switch to ZGC. G1GC struggles above 32GB. |
| > 32GB | Any | Must use ZGC. G1GC with > 32GB loses compressed oops. |

### GC Algorithm Decision

```
Should I switch from G1GC to ZGC?
├── Heap > 16GB → Consider ZGC (valid alternative, weigh CPU cost)
├── Heap > 24GB → Recommend ZGC (G1GC region management gets harder)
├── Heap > 32GB → Switch to ZGC (mandatory; G1GC struggles above 32GB)
├── JDK < 17 → Stay on G1GC (ZGC not production-ready)
├── JDK 17-20 → ZGC viable but no generational mode
├── JDK 21+ → ZGC with generational mode is excellent
├── CPU cores < 4 → Stay on G1GC (ZGC needs concurrent threads)
├── Pause tolerance < 10ms → ZGC
└── Mostly young-gen churn with small heap → G1GC (ZGC overhead not worth it)
```

---

## Common GC Anti-Patterns

| Anti-Pattern | Symptom | Root Cause | Fix |
|-------------|---------|-----------|-----|
| Too small heap | Frequent Full GC, OOM errors | < 6GB for active server | Increase to at least 8-10GB |
| Wrong GC for workload | ZGC on 4GB heap, G1GC on 64GB heap | Misunderstanding of GC strengths | See GC algorithm decision tree |
| Missing AlwaysPreTouch | Micro-stalls during warmup | Lazy page commitment | Add -XX:+AlwaysPreTouch |
| Xms != Xmx | Periodic GC spikes from heap resize | JVM expanding/contracting heap | Set Xms = Xmx |
| Missing ParallelRefProcEnabled | Longer GC pauses than necessary | Single-threaded reference processing | Add the flag |
| Too high MaxGCPauseMillis | G1 not aggressive enough | Target too relaxed | Set to 200 (Aikar's) |
| Too low MaxGCPauseMillis | Excessive GC frequency, more overhead | G1 over-correcting | Set to 200 |
| Ignoring System.gc() | Unpredictable full GCs | Plugins calling System.gc() | Add -XX:+DisableExplicitGC |
| G1 with default IHOP (45%) | Old gen fills before concurrent mark | Default triggers too late | Set to 15 (Aikar's) |
| G1 with default NewSizePercent (5%) | Tiny young gen, constant minor GCs | Young gen too small for MC | Set to 30 (Aikar's) |
| ZGC without generational mode | Allocation stalls on JDK 21+ | Not using generational feature | Add -XX:+ZGenerational |
| Compressed Oops disabled | 32GB+ heap with G1GC | Loses ~40% effective memory from pointer size | Stay ≤ 31GB or switch to ZGC + 40GB+ |

### Memory Leak Indicators

| Indicator | How to Detect | Common Causes |
|-----------|-------------|---------------|
| Old gen monotonically increasing | GC log or VisualVM over time | Plugin caching without eviction |
| Full GC frees very little | < 10% freed by Full GC | True leak (unreachable but not collected) |
| Heap dump shows unexpected dominator | Eclipse MAT dominator tree | Large maps/caches in plugins |
| Metaspace growing | `jcmd VM.metaspace` | Class loader leak (hot-reload plugins) |
| Direct buffer memory growing | `jcmd VM.native_memory` | Netty buffer leaks in proxy/plugins |