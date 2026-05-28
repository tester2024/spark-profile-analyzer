# Folia/Canvas Thread Analysis Reference

Diagnosing performance on Folia and Canvas servers requires fundamentally different thread health assessment than standard Paper/Spigot servers. This reference covers the threading model, idle frame recognition, `spark_toolkit.py` commands tuned for region threads, and configuration recommendations.

---

## 1. Overview of Folia/Canvas Threading Model

### What is Folia

Folia is a Paper fork that replaces the single main-thread tick loop with parallel region-based ticking. The world is partitioned into independent regions, each ticking on its own thread. This eliminates the single-threaded bottleneck that limits Paper servers to ~50-100 players.

### What is Canvas

Canvas is a Folia fork with additional optimizations: an `AffinitySchedulerThreadPool` that assigns region threads to CPU cores with affinity, async chunk loading, async mob spawning, and vectorized entity processing. Canvas requires `--add-modules=jdk.incubator.vector` at JVM startup.

### How Region Threads Work

| Component | Class | Role |
|----------|-------|------|
| Region Scheduler | `io.papermc.paper.threadedregions.TickRegionScheduler` | Splits world into independent regions, assigns each to a thread |
| Tick Thread Runner | `io.papermc.paper.threadedregions TickRegionScheduler$TickThreadRunner` | Executes the tick loop for assigned region(s) |
| Region Queue | `io.papermc.paper.threadedregions.RegionizedTaskQueue$RegionQueue` | Per-region task queue for ticking and scheduling |
| Schedule Handle | `io.papermc.paper.threadedregions.RegionScheduleHandle` | Handle for scheduling tasks on a specific region |
| Affinity Pool (Canvas) | `com.mojang.util.AffinitySchedulerThreadPool$TickThreadRunner` | Canvas-specific thread runner with CPU affinity |

Each region is an independent area around one or more players, separated by at least 8 chunks of empty space from other regions. Regions merge when players move close together and split when they spread apart.

### Why Standard Thread Health Assessment Fails for Folia

Standard Spark thread analysis counts `Thread.sleep()`, `Object.wait()`, and `LockSupport.park()` as idle/sleep time. On Folia/Canvas, region threads use **native parking** (`pthread_cond_wait`, `pthread_cond_timedwait`, `parkNanos`) to wait for the next tick. These are **not** captured by Spark's sleep detection because they appear as native method frames, not Java sleep frames.

**Result**: All region threads report 0% sleep, which makes them appear OVERLOADED when they are actually idle most of the time. This is the core issue identified in the skill-rate.md review — the toolkit must recognize these native idle patterns.

The `spark_toolkit.py` v2 fix uses `_is_idle_frame()` and `effective_idle_pct` to account for both Java sleep and native idle frames. The `threads` command now reports:

| Field | Meaning |
|-------|---------|
| `sleep_time` | Java-level sleep/wait time only (what standard Spark reports) |
| `native_idle_time` | Time in native parking/waiting that is actually idle |
| `effective_idle_time` | `sleep_time + native_idle_time` |
| `effective_idle_pct` | `(sleep_time + native_idle_time) / total_time * 100` |
| `health` | Based on `effective_idle_pct`, not `sleep_pct` alone |

---

## 2. Thread Types in Folia/Canvas

| Thread | Name Pattern | Count | Purpose | Idle Method |
|--------|-------------|-------|---------|--------------|
| Folia Region Scheduler Thread | `Folia Region Scheduler Thread #N` | Typically `cpu-2` or configured | Actual tick workers | `waitUntilDeadline` / `parkNanos` |
| AffinitySchedulerThreadPool$TickThreadRunner (Canvas) | `TickThreadRunner-N` or `Folia Region Scheduler Thread #N` | Configured via `region-thread-count` | Canvas tick workers with CPU affinity | `waitUntilDeadline` / `parkNanos` |
| Netty Worker | `netty-worker-N-M` | Auto (= CPU cores) | Network packet I/O | `epoll_pwait2` / `epoll_pwait` |
| Server Main Thread | `Server thread` | 1 | Global region ticking (nether roof, end, global schedulers) | `waitForNextTick` |
| Scheduled Pool | `pool-N-thread-M` | 2-4 | Async plugin tasks | `park` / `pthread_cond_wait` |
| Chunk I/O | `Chunk I/O Worker Thread-N` | 2-4 | Chunk load/save | Native I/O wait |
| GC Thread | `GC Thread-N` | Auto | Garbage collection | N/A (should not be profiled) |

---

## 3. Recognizing Idle vs Active in Folia

### Idle Frame Signatures

These stack trace frames indicate a thread is **idle** (waiting for work), not doing active work. They must be treated as idle time in any health assessment.

| Frame | Thread | Meaning |
|-------|--------|---------|
| `AffinitySchedulerThreadPool$TickThreadRunner.waitUntilDeadline` | Region threads (Canvas) | Thread is parked waiting for the next tick deadline |
| `TickRegionScheduler$TickThreadRunner.waitUntilDeadline` | Region threads (Folia) | Thread is parked waiting for the next tick deadline |
| `TickRegionScheduler$TickThreadRunner.waitForTick` | Region threads (Folia) | Thread is waiting for tick signal |
| `LockSupport.parkNanos` | Any thread | Native parking, often tick-wait in Folia |
| `LockSupport.park` | Any thread | Native parking |
| `pthread_cond_wait` | Any thread | Native condition wait (C library) |
| `pthread_cond_timedwait` | Any thread | Native timed condition wait — most common idle for region threads |
| `epoll_pwait2` | Netty threads | Epoll wait for I/O events |
| `epoll_pwait` | Netty threads | Epoll wait for I/O events |
| `epoll_wait` | Netty threads | Epoll wait for I/O events |
| `RegionizedTaskQueue$RegionQueue.scheduledInternal` | Region threads | Region queue is idle with no pending tasks |

### Active Frame Signatures (Region Threads Doing Real Work)

| Frame | Meaning |
|-------|---------|
| `MinecraftServer.tickServer` | Main tick loop executing |
| `MinecraftServer.tickRegion` | Region tick main loop — actual game processing |
| `Level.tick` | World ticking |
| `Level.tickEntities` or `ServerLevel.tickEntities` | Entity ticking phase |
| `Level.tickNonPassengerEntities` or `forEachTickingEntity` | Iterating and ticking entities |
| `ServerLevel.tickBlockEntities` | Block entity (tile entity) ticking |
| `ChunkMap.tick` | Chunk map maintenance |
| `Connection.tick` | Network packet processing for region |
| `MinecraftServer.scheduleTick` | Scheduled task execution |

### How spark_toolkit.py Handles This

The toolkit's `_is_idle_frame()` function (in `spark_toolkit.py`) checks both Java sleep methods and native idle methods:

```python
SLEEP_METHODS = {
    "waitfornexttick", "thread.sleep", "locksupport.park", "object.wait",
    "unsafe.park", "park", "parknanos", "parkuntil",
}

NATIVE_IDLE_METHODS = {
    "pthread_cond_wait", "pthread_cond_timedwait", "pthread_cond_signal",
    "pthread_mutex_lock", "pthread_mutex_unlock",
    "epoll_wait", "epoll_pwait", "epoll_pwait2",
    "waituntildeadline", "waitfortick",
    "futex_wait", "futex_wake",
    "__nanosleep", "__poll", "__select", "__accept",
    "socketaccept",
    "native_epoll_wait",
}

FOLIA_CANVAS_IDLE_PATTERNS = [
    "affinityschedulerthreadpool$tickthreadrunner.waituntildeadline",
    "affinityschedulerthreadpool$tickthreadrunner.waitfortick",
    "tickregionScheduler$regionizedtaskqueue$regionqueue.scheduledinternal",
    "regionizedtaskqueue",
    "regionscheduler$regionschedulehandle",
]
```

For Folia/Canvas region threads (detected via `_is_folia_region_thread()`), `native_idle_time` is added to `sleep_time` to produce `effective_idle_pct`. This is the percentage used for health assessment instead of `sleep_pct` alone.

---

## 4. Folia-Specific Thread Health Assessment

### The Problem with Standard sleep_pct

On a standard Paper server, the Server Main Thread's `sleep_pct` directly indicates how idle the thread is. If `sleep_pct` is 60%, the thread has 60% of its time in `Thread.sleep()` between ticks, meaning it's healthy.

On Folia, region threads use `LockSupport.parkNanos()` and native `pthread_cond_timedwait()` to wait for the next tick. These are **not** captured as Java sleep by Spark. The result:

| Metric | Paper Server Main Thread | Folia Region Thread (idle) | Folia Region Thread (busy) |
|--------|--------------------------|------------------------------|----------------------------|
| `sleep_pct` | 60% | 0% | 0% |
| `native_idle_pct` | 0% | 75% | 5% |
| `effective_idle_pct` | 60% | 75% | 5% |
| Health (old) | HEALTHY | OVERLOADED | OVERLOADED |
| Health (new) | HEALTHY | HEALTHY | OVERLOADED |

Without accounting for native idle, **every Folia region thread appears OVERLOADED** regardless of actual load. With `effective_idle_pct`, the health assessment is correct.

### New Thresholds (effective_idle_pct)

| Rating | effective_idle_pct | Description |
|--------|-------------------|-------------|
| HEALTHY | >= 50% | Region thread has ample idle time between ticks. Server is not overloaded. |
| MODERATE | 20-50% | Region thread is busy but keeping up. Monitor for degradation. |
| OVERLOADED | < 20% | Region thread is saturated. Active tick work exceeds available time. Lag imminent or present. |

These thresholds match the standard `sleep_pct` thresholds but use `effective_idle_pct` instead, which includes native parking/waiting as idle time.

### Interpreting the threads Command on Folia

```bash
python spark_toolkit.py threads profile.sparkprofile --thread Region
```

Sample output for a healthy Folia server:

```json
{
  "name": "Folia Region Scheduler Thread #3",
  "total_time": 150000,
  "sleep_time": 0,
  "native_idle_time": 98000,
  "effective_idle_time": 98000,
  "effective_idle_pct": 65.33,
  "active_time": 52000,
  "active_pct": 34.67,
  "tick_time": 42000,
  "tick_pct": 28.0,
  "other_time": 10000,
  "is_folia_region_thread": true,
  "health": "HEALTHY"
}
```

Key fields:
- `sleep_time: 0` — confirms this is a Folia thread (no Java sleep)
- `native_idle_time: 98000` — time spent in native parking (actually idle)
- `effective_idle_pct: 65.33` — real idle percentage, used for health
- `active_pct: 34.67` — time doing actual game work
- `tick_pct: 28.0` — time in `tick`/`doTick`/`runTick` frames specifically

---

## 5. Analyzing Region Thread Performance

### Quick Health Check

```bash
# View all region threads with effective idle assessment
python spark_toolkit.py threads profile.sparkprofile --thread Region

# View top 5 busiest region threads
python spark_toolkit.py threads profile.sparkprofile --thread Region --top-threads 5
```

Look for:
- All threads HEALTHY with effective_idle_pct >= 50%: server is fine
- Some MODERATE with effective_idle_pct 20-50%: region imbalance, some regions have more load
- Any OVERLOADED with effective_idle_pct < 20%: that region is saturated, lag present

### Finding Active Work Hotspots

```bash
# Hotspots excluding idle frames on region threads
python spark_toolkit.py hotspots profile.sparkprofile --thread Region --exclude-sleep --min-pct 1

# Hotspots on a specific region thread
python spark_toolkit.py hotspots profile.sparkprofile --thread "Folia Region Scheduler Thread #0" --exclude-sleep --min-pct 0.5
```

The `--exclude-sleep` flag now filters both Java sleep frames AND native idle frames (via `_is_idle_frame()`), so on Folia/Canvas you get only active work hotspots.

### Drill Into Call Tree

```bash
# Call tree for region threads, filtering out low-percentage noise
python spark_toolkit.py tree profile.sparkprofile --thread "Folia Region" --min-pct 0.5 --limit 30

# Call tree for a specific busy region thread
python spark_toolkit.py tree profile.sparkprofile --thread "Folia Region Scheduler Thread #7" --min-pct 1 --limit 20
```

### Expected Folia Call Signatures

When analyzing region thread call trees, look for these key method signatures:

| Signature | Meaning | Typical % | When to Investigate |
|-----------|---------|-----------|-------------------|
| `MinecraftServer.tickServer` / `tickRegion` | Region tick main loop | 5-15% | Normal entry point |
| `Level.tick` | World tick processing | 10-30% | Normal for active regions |
| `Level.tickEntities` / `forEachTickingEntity` | Entity tick iteration | 20-60% | > 50% indicates too many entities |
| `ServerLevel.tickBlockEntities` | Tile entity processing | 5-15% | > 15% indicates too many hoppers/chests |
| `Connection.tick` | Network processing for this region | 2-10% | > 10% indicates packet flood |
| `MinecraftServer.scheduleTick` | Scheduled task execution | 1-5% | > 10% indicates plugin scheduled task overload |

If `forEachTickingEntity` dominates (>50% of active time), entity optimization is the primary fix:
- Reduce `entity-activation-range` in `paper-global.yml`
- Reduce `spawn-limits` in `paper-world.yml`
- Increase `mob-spawn-rate` intervals
- Check for mob farms in the overloaded region

### Plugin Attribution on Region Threads

```bash
# Which plugins consume time on region threads
python spark_toolkit.py plugins profile.sparkprofile --thread Region

# Deep-dive into a specific plugin's region thread usage
python spark_toolkit.py tree profile.sparkprofile --thread Region --plugin "com.example" --min-pct 0.5
```

### Region Imbalance Diagnosis

If some region threads are OVERLOADED while others are HEALTHY:

1. Check which regions are overloaded:
   ```bash
   python spark_toolkit.py threads profile.sparkprofile --thread Region --top-threads 16
   ```
2. Find what the overloaded threads are doing:
   ```bash
   python spark_toolkit.py hotspots profile.sparkprofile --thread "Region Scheduler Thread #7" --exclude-sleep --min-pct 1
   ```
3. Common causes of region imbalance:
   - Mob farm or spawner in one region
   - Heavy redstone in one region
   - Player cluster (market, spawn) in one region
   - Cross-region synchronization overhead (portals, teleports)

---

## 6. Canvas-Specific Considerations

### AffinitySchedulerThreadPool vs Standard Folia Scheduler

| Aspect | Folia (Standard) | Canvas |
|--------|-------------------|--------|
| Thread pool | `TickRegionScheduler` manages region threads | `AffinitySchedulerThreadPool` manages threads with CPU affinity |
| Thread naming | `Folia Region Scheduler Thread #N` | May use `TickThreadRunner-N` or same naming convention |
| CPU affinity | OS schedules threads freely | Threads pinned to CPU cores for cache locality |
| Idle mechanism | `waitUntilDeadline` / `parkNanos` | Same native parking, but may use `futex_wait` on Linux |
| Config file | `paper-global.yml` | `paper-global.yml` + `canvas-server.json5` |

The `_is_folia_region_thread()` function detects both Folia and Canvas region threads by checking for "region", "folia", "canvas", or "tickthreadrunner" in the thread name.

### JVM Flag Requirement

Canvas **requires** `--add-modules=jdk.incubator.vector` in the JVM startup flags. Without this flag, Canvas will fail to start or fall back to scalar operations, losing the performance benefit of vectorized entity processing.

Verify in `spark_toolkit.py info` output that the JVM flags include this module. If missing, add to startup script:
```bash
--add-modules=jdk.incubator.vector
```

### Canvas-Specific Config Options (canvas-server.json5)

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `performance.enable-async-chunks` | Async chunk loading | true | true | Distributes chunk I/O off region threads |
| `performance.enable-async-mobs` | Async mob spawning | true | true | Distributes mob spawn calculations |
| `performance.optimized-dns` | Faster DNS resolution | true | true | Reduces login delay |
| `packets.rewrite-all` | Packet rewriting optimization | true | true | Canvas-specific packet optimization |
| `misc.disable-method-profiling` | Disable method profiling | false | false (keep for Spark) | May reduce overhead slightly but loses profiling data |

### Canvas Thread Count Recommendations

| CPU Cores | Region Threads | I/O Threads | Notes |
|-----------|---------------|-------------|-------|
| 4 | 2 | 1 | Minimum viable. Canvas will struggle with many players. |
| 8 | 4 | 2 | Good for 50-100 players. |
| 16 | 8 | 4 | Sweet spot for 100-200 players. |
| 32 | 16 | 8 | Handles 200-400+ players. |
| 64 | 32 | 16 | Large-scale, 400+ players. |

**Formula**: `region_threads = max(cpus / 2, 4)` for most servers. Reserve half the cores for I/O, GC, Netty, and OS.

Canvas's affinity scheduler benefits from matching region thread count to physical cores (not logical/hyperthreaded cores). On a 16-core/32-thread CPU, use 8-16 region threads, not 32.

---

## 7. Folia/Canvas Config Recommendations

### Region Threading Config (paper-global.yml)

```yaml
threaded-regions:
  region-thread-count: <see formula below>
  io-thread-count: <auto or cpu/4>
```

**Region thread count formula**:
- Minimum: 4
- Maximum: physical CPU cores
- **Recommended**: `max(cpus / 2, 4)` for most servers
- High-player-count servers (200+): `cpus - 4` (reserve for I/O and GC)

### View Distance vs Simulation Distance

These settings work differently on Folia than Paper:

| Config | Paper Behavior | Folia Behavior |
|--------|---------------|----------------|
| `view-distance` | Chunks sent to client AND ticking radius | Chunks sent to client only. Region threads handle ticking independently. |
| `simulation-distance` | Chunks where entities tick | **Ignored on Folia.** Regions define their own tick boundaries. |

On Folia, you can safely increase `view-distance` higher than Paper because ticking is decoupled from view distance. However, higher view distance still increases:
- Memory (loaded chunks)
- Network bandwidth (more chunks to send)
- Client-side rendering load

**Recommended**:

| Server Size | view-distance | Notes |
|-------------|--------------|-------|
| Small (<50 players) | 8-10 | Good visibility, regions handle ticking |
| Medium (50-200) | 6-8 | Balance visibility and network load |
| Large (200+) | 4-6 | Reduce network load; regions still tick correctly |

### Entity Activation Ranges

On Folia, entity activation ranges still apply within each region. Use the same values as Paper:

```yaml
# paper-global.yml
entity-activation-range:
  animals: 16-24
  monsters: 24
  raiders: 32
  misc: 8
  water: 8-16
  villagers: 16-24
  flying-monsters: 32
```

### Spawn Limits

Folia uses per-player spawn limits like Paper, but within each region. This means total mob count scales with (players × regions), not just players. If 4 players are in 4 separate regions, each region has its own spawn budget.

```yaml
# paper-world.yml
spawn-limits:
  monster: 30-50    # Lower than Paper since multiplied by regions
  animal: 5-8
  water-creature: 3
  water-ambient: 5
  ambient: 2
```

### Parallel Scheduling Concepts

| Concept | Description |
|---------|-------------|
| **Region threads** | Each region is an independent area around a player group. Separated by > 8 chunks of empty space. |
| **Tick independence** | Each region ticks independently. Lag in one region does NOT affect another. |
| **Entity tracking** | Entities in different regions are processed by different threads simultaneously. |
| **Cross-region operations** | Portal teleports, cross-region entity moves, global schedulers are batched and processed on the global region thread. |
| **Global region** | The nether roof, end, and some scheduled tasks run on a global region thread. Monitor this separately. |
| **Region merging/splitting** | When players move close together, their regions merge. When they spread apart, regions split. This is normal but can cause transient lag. |

---

## 8. Common Folia/Canvas Performance Issues

| Issue | Detection Command | Root Cause | Fix |
|-------|-------------------|------------|-----|
| All region threads showing OVERLOADED (sleep_pct=0%) | `threads --thread Region` shows effective_idle_pct < 20% for all threads | Standard sleep_pct doesn't count native parking as idle. Use effective_idle_pct. | Already fixed in spark_toolkit.py. Use `threads` command which reports `effective_idle_pct`. |
| Region thread imbalance (some OVERLOADED, some HEALTHY) | `threads --thread Region --top-threads 16` — wide spread in effective_idle_pct | One region has concentrated load (mob farm, player hub, redstone) | Spread players, cap entities in dense regions, reduce view-distance for problem areas |
| Cross-region synchronization overhead | `hotspots --thread "Server thread" --exclude-sleep --min-pct 1` shows global scheduler time high | Cross-region operations batched on global thread | Reduce portal usage, batch cross-region tasks, avoid cross-region redstone |
| Entity tick dominating (forEachTickingEntity > 50% active) | `tree --thread Region --min-pct 0.5` shows forEachTickingEntity as top consumer | Too many entities per region | Reduce spawn-limits, increase mob-spawn-rate intervals, lower activation range |
| Chunk loading blocking region threads | `hotspots --thread Region --exclude-sleep --min-pct 1` shows chunk load methods | Region thread doing sync chunk I/O instead of async | Enable async chunks in Canvas, pre-generate worlds with Chunky |
| Wrong thread count (too many or too few regions) | `threads` shows all threads MODERATE/OVERLOADED (too few) or all HEALTHY with high idle (too many) | Misconfigured region-thread-count | Use formula `max(cpus/2, 4)`. Too many threads = context switching overhead. Too few = queue backup. |
| Canvas missing jdk.incubator.vector module | `info` shows JVM flags without `--add-modules=jdk.incubator.vector` | Canvas cannot use vectorized operations | Add `--add-modules=jdk.incubator.vector` to JVM startup flags |
| Global region thread bottleneck | `threads --thread Server` shows Server Main Thread OVERLOADED | Nether portals, end gateways, global scheduled tasks | Reduce global scheduled tasks, limit portal usage, move tasks to region schedulers |
| Netty threads showing high load | `threads --thread netty` shows effective_idle_pct < 30% | High packet volume, large view distance, entity tracking | Reduce view-distance, lower entity-tracking-range, increase network-compression-threshold |
| GC pausing all region threads simultaneously | `gc` shows frequent STW pauses; all regions spike MSPT together | GC STW pauses affect all threads | Increase heap, tune GC (see jvm-gc-tuning.md), consider ZGC |

---

## 9. Commands Reference for Folia Analysis

### Initial Health Assessment

```bash
# 1. Identify server platform and threading model
python spark_toolkit.py info profile.sparkprofile

# 2. Check TPS and MSPT for the global region
python spark_toolkit.py tps profile.sparkprofile

# 3. Check ALL threads with effective idle assessment
python spark_toolkit.py threads profile.sparkprofile
```

### Region Thread Analysis

```bash
# 4. List all region threads with health status
python spark_toolkit.py threads profile.sparkprofile --thread Region

# 5. Top 5 busiest region threads by active time
python spark_toolkit.py threads profile.sparkprofile --thread Region --top-threads 5

# 6. Specific region thread detail
python spark_toolkit.py threads profile.sparkprofile --thread "Folia Region Scheduler Thread #7"
```

### Finding Lag on Region Threads

```bash
# 7. Hotspots across all region threads, excluding idle time
python spark_toolkit.py hotspots profile.sparkprofile --thread Region --exclude-sleep --min-pct 1

# 8. Entity tick specifically (look for forEachTickingEntity)
python spark_toolkit.py search profile.sparkprofile "forEachTickingEntity" --thread Region

# 9. Call tree for a specific busy region
python spark_toolkit.py tree profile.sparkprofile --thread "Folia Region Scheduler Thread #7" --min-pct 0.5 --limit 30

# 10. Plugin attribution on region threads
python spark_toolkit.py plugins profile.sparkprofile --thread Region
```

### Global Thread and Network Analysis

```bash
# 11. Main thread analysis (global region)
python spark_toolkit.py hotspots profile.sparkprofile --thread Server --exclude-sleep --min-pct 1

# 12. Netty thread analysis
python spark_toolkit.py threads profile.sparkprofile --thread netty
python spark_toolkit.py hotspots profile.sparkprofile --thread netty --exclude-sleep --min-pct 0.5

# 13. GC analysis
python spark_toolkit.py gc profile.sparkprofile
```

### Full Report

```bash
# 14. Complete analysis (includes threads, hotspots, GC, entity stats, TPS)
python spark_toolkit.py report profile.sparkprofile
```

### Interpreting Results — Common Patterns

**Pattern: All region threads HEALTHY, TPS good**
- Server is running well. No action needed.

**Pattern: 1-2 region threads OVERLOADED, others HEALTHY**
- Region imbalance. Identify the busy threads' hotspots and reduce load in that area.
- Common causes: mob farm, player hub, heavy redstone in one region.
- Fix: Spread players, cap entities in dense regions, relocate farms.

**Pattern: Most region threads MODERATE, TPS dipping**
- System-wide load. Consider increasing region-thread-count or reducing overall entity/chunk load.
- Check if `forEachTickingEntity` is the dominant cost. If so, reduce spawn-limits and activation range.

**Pattern: Global thread (Server Main) OVERLOADED**
- Cross-region operations bottlenecking.
- Check for portal-heavy gameplay, global scheduled tasks, or nether/end lag.
- Move plugin tasks to region schedulers where possible.

**Pattern: Netty threads OVERLOADED**
- Network packet volume too high.
- Reduce view-distance, lower entity-tracking-range, increase network-compression-threshold.

**Pattern: All threads showing 0% sleep (even non-region threads)**
- This may indicate a profiling issue — ensure `--exclude-sleep` is used with hotspots.
- For `threads` output, check `effective_idle_pct` instead of `sleep_pct`.
- If `effective_idle_pct` is also near 0% for all threads, the server is genuinely overloaded.