# Memory Leak Detection

How to identify, diagnose, and resolve memory leaks in Minecraft servers using Spark profiler data and heap dump analysis.

---

## What Is a Memory Leak

### Definition

A memory leak occurs when objects are no longer needed by the application but cannot be garbage collected because they remain reachable through a reference chain. The JVM has no way to know the programmer intended these objects to be discarded.

### Leak vs Bloat vs High Usage

| Type | Definition | Pattern | Example |
|------|-----------|---------|---------|
| **Memory Leak** | Unreachable-from-logic objects retained by stale references | Heap grows monotonically, GC recovers nothing | Static map never cleared, listener never unregistered |
| **Memory Bloat** | Reachable objects that are larger or more numerous than necessary | Heap is high but stable, GC cannot help | 10,000 cached player objects, oversized buffers |
| **High Usage** | Legitimate demand exceeding available resources | Heap fills under load, empties when load drops | Many players online, large worlds loaded |

**Key distinction**: If a Full GC recovers < 10% of heap, it's likely a leak. If Full GC recovers > 30% but heap re-fills quickly, it's bloat. If Full GC recovers well and heap stays proportional to load, it's high usage.

---

## Detecting Leaks from Spark Data

### Using `spark_toolkit.py heap`

The `heap` command shows top heap consumers by object type with plugin attribution.

```bash
python spark_toolkit.py heap <source>
python spark_toolkit.py heap <source> --type-filter "net.minecraft" --limit 20
python spark_toolkit.py heap <source> --plugin "com.example" --limit 10
```

**What to look for in `heap` output**:

| Observation | Likely Cause | Next Step |
|-------------|-------------|-----------|
| Single type > 20% of heap | Bloat or leak in that type | Run `plugin-heap` to attribute |
| `byte[]` or `char[]` dominating | Large buffers or strings retained | Check what holds references via heap dump |
| `HashMap$Node` in top 10 | Cache or map growing without bounds | Find the map owner via `plugin-heap` |
| Entity types > 5% of heap | Entity accumulation | Check entity limits, despawn ranges |
| `CompoundTag` (NBT) > 10% | NBT bloat | Check tile entity data, player data files |

### Using `spark_toolkit.py plugin-heap`

Attributes heap memory to a specific plugin, showing matched types, total size, instance count, percentage of total heap, and severity assessment.

```bash
python spark_toolkit.py plugin-heap <source> --plugin "Essentials"
python spark_toolkit.py plugin-heap <source> --plugin "com.example.myplugin"
```

**Severity levels**:

| Level | Threshold | Action |
|-------|-----------|--------|
| CRITICAL | > 10% of heap | Investigate immediately |
| WARNING | > 5% of heap | Monitor and plan fix |
| LOW | <= 5% of heap | Acceptable |

**Leak indicators in plugin-heap output**:

| Signal | Meaning |
|--------|---------|
| Instance count growing over time (compare profiles) | Objects accumulating, likely leak |
| Size percentage increasing each profile | Plugin consuming more heap over time |
| `HashMap`, `ConcurrentHashMap` dominance | Unbounded cache |
| `ArrayList` dominance | Growing list never trimmed |

### Using `spark_toolkit.py gc`

The `gc` command shows GC statistics with health status. This is the primary tool for detecting memory pressure that indicates a leak.

```bash
python spark_toolkit.py gc <source>
```

**Key GC metrics for leak detection**:

| GC Field | Leak Indicator | Threshold |
|----------|---------------|-----------|
| Old gen usage | Monotonically increasing after each cycle | Grows > 5% between profiles |
| Full GC count | Non-zero and increasing | Any Full GC = investigate |
| Full GC freed | Very little memory recovered | < 10% freed = likely leak |
| Young GC frequency | Increasing over time | Frequency doubles = allocation storm or promotion leak |
| Total GC time % | Increasing over time | > 10% = GC thrashing from memory pressure |
| Mixed GC frequency | Increasing (G1) | Old gen filling faster than it can be collected |

### Using `spark_toolkit.py plugin-profile`

Complete plugin analysis combining CPU hotspots, heap usage, allocation patterns, and auto-generated findings.

```bash
python spark_toolkit.py plugin-profile <source> --plugin "MyPlugin"
```

**Leak-specific findings from plugin-profile**:

| Finding Type | What It Detects |
|-------------|---------------|
| Heap dominance | Plugin using disproportionate heap share |
| Allocation hotspots | Methods creating most objects per tick |
| GC pressure | Plugin causing above-average GC activity |
| Growth trend | Instance counts increasing over sampling period |

### Spark Heap Data Patterns

Take two Spark profiles 30-60 minutes apart and compare.

| Pattern | How It Appears in Spark | Diagnosis |
|---------|----------------------|-----------|
| Old gen monotonically growing | `heap` shows increasing total, `gc` shows old gen rising each check | Objects promoted but never collected = leak |
| Allocation rate spike | `gc` shows young GC frequency doubling, `heap` shows inflated young gen | Sudden burst of object creation, possibly short-term but check if it persists |
| GC thrashing | `gc` shows > 20% time in GC, frequent Full GC | Heap too small or leak filling old gen |
| Stable high usage | `heap` stays high but stable, `gc` recovers well with Full GC | Bloat, not a leak - reduce cache sizes |
| Metaspace growing | Not directly in Spark, but `gc` may show class loading pressure | Classloader leak, typically from hot-reloading plugins |

---

## Spark GC Indicators of Leaks

### GC Indicator Thresholds

| Indicator | What to Look For | GOOD | WARNING | CRITICAL | Leak Probability |
|-----------|-----------------|------|---------|-----------|-----------------|
| Old gen growth (G1) | Old gen % increases between GC cycles | < 1%/min | 1-3%/min | > 3%/min | High at WARNING+ |
| Full GC recovery (G1) | % of heap freed by Full GC | > 50% | 10-50% | < 10% | Certain at < 10% |
| Young GC frequency | Events per second, trend over time | < 0.5/s | 0.5-2/s | > 2/s | High if increasing |
| Mixed GC frequency (G1) | Increasing rate | Stable | Slowly increasing | Rapidly increasing | Medium at increasing |
| Total GC time | % of profile time in GC | < 3% | 3-10% | > 10% | Possible at > 5% |
| ZGC cycle frequency | Major cycles per minute | < 5/min | 5-15/min | > 15/min | Medium if increasing |
| ZGC allocation stalls | Any stalls | 0 | 0 | > 0 | High if persistent |
| Promoted to old gen | Survivor space always full | < 50% | 50-80% | > 80% | Medium at > 80% |
| GC pause trend | Pauses lengthening over time | Stable | Slowly growing | Rapidly growing | Medium if growing |
| Heap after GC | Post-GC heap usage | < 50% | 50-70% | > 70% | High if monotonically increasing |

### Old Gen Monotonic Growth

The strongest leak signal. After each GC cycle (including Full GC), old gen usage should drop. If it only grows:

```
Time 0min:  Old gen 45%  (after Full GC)
Time 15min: Old gen 52%  (after Full GC)
Time 30min: Old gen 58%  (after Full GC)
Time 45min: Old gen 65%  (after Full GC)
Time 60min: Old gen 71%  (after Full GC)
→ Monotonic growth of ~0.9%/min = LEAK CONFIRMED
```

**How to detect with Spark**:

1. Take profile every 15 minutes for 1 hour
2. Run `spark_toolkit.py gc <source>` for each profile
3. Compare old gen usage after Full GC across profiles
4. If old gen grows > 5% across the hour, a leak is present

**Causes by growth rate**:

| Growth Rate | Likely Type | Typical Cause |
|-------------|-------------|---------------|
| < 0.5%/hour | Slow leak, possibly bloat | Small cache growing, log buffer |
| 0.5-2%/hour | Moderate leak | Player data cache, event listener accumulation |
| 2-5%/hour | Fast leak | Entity accumulation, chunk loading leak |
| > 5%/hour | Severe leak | Major collection leak, ThreadLocal leak, Netty buffer leak |

### Full GC Frees Little Heap

A Full GC stops the world and collects everything possible. If it frees very little:

| Full GC Recovery | Diagnosis | Action |
|-----------------|-----------|--------|
| > 50% | Normal GC behavior | Likely bloat, not leak |
| 30-50% | Moderate retention | Some objects long-lived, possibly cache |
| 10-30% | Concerning | Likely leak or excessive cache |
| < 10% | Confirmed leak | Take heap dump immediately |
| < 5% | Severe leak | OOM imminent, take action now |

**How to read full GC recovery from Spark GC output**:
- Look at `total_before_gc` vs `total_after_gc` for Full GC events
- If `after_gc` is > 90% of `before_gc`, almost nothing was collected
- This means nearly all objects are still reachable = leak

### Young GC Frequency Increasing (Allocation Storms)

When young GC frequency increases over time, it can indicate:

| Pattern | Meaning | Distinction |
|---------|---------|-------------|
| Young GC frequency increases, old gen stable | More short-lived objects (allocation storm) | Not a leak per se, but causes GC pressure |
| Young GC frequency increases, old gen grows | Objects being promoted and not collected | Leak in old gen |
| Young GC frequency spikes then returns | Temporary burst (startup, mass join) | Normal, not a leak |
| Young GC frequency steadily increases over hours | Growing problem (leak or increasing load) | Investigate: leak if player count is stable |

### Metaspace Growth

Metaspace stores class metadata. It grows when classloaders load new classes and doesn't shrink when they're unreferenced if the classloader itself is leaked.

| Observation | Meaning | Action |
|-------------|---------|--------|
| Metaspace grows during plugin load | Normal | None |
| Metaspace grows continuously in steady state | Classloader leak | Check for hot-reloading plugins |
| Metaspace doesn't shrink after plugin unload | Classloader not GC'd | Plugin not properly cleaning up |
| `Metaspace OOM` error | Metaspace exhausted | Increase MaxMetaspaceSize, fix classloader leak |

**Check metaspace**:

```bash
# Linux
jcmd <pid> VM.metaspace

# Or via Spark: look for class loading in gc output
spark_toolkit.py gc <source>
```

---

## Detecting Leaks from Heap Dumps

### Using `heapdump_analyzer.py analyze`

Analyzes a jmap histogram file, classifying object types, identifying dominance patterns, and flagging known Minecraft leak signatures.

```bash
# From a jmap histogram file
python heapdump_analyzer.py analyze --jmap-histogram histogram.txt

# With total heap size for percentage calculations
python heapdump_analyzer.py analyze --jmap-histogram histogram.txt --total-heap 8589934592

# From a running process (auto-detects PID)
python heapdump_analyzer.py analyze --pid 12345

# Write output to file
python heapdump_analyzer.py analyze --jmap-histogram histogram.txt -o analysis.json
```

**What `analyze` reports**:

| Section | Content |
|---------|---------|
| `top_consumers` | Top 20 object types by size with instance counts |
| `dominance_analysis` | Identifies types dominating > 15% of heap |
| `leak_signatures` | Matches against known Minecraft leak patterns with risk levels |
| `distribution` | Breakdown by category (entity, chunk, NBT, plugin, etc.) |
| `recommendations` | Actionable findings based on detected patterns |

**Leak pattern thresholds used by the analyzer**:

| Pattern | Threshold | Risk |
|---------|-----------|------|
| String dominance | > 30% of heap | MEDIUM |
| byte[] dominance | > 25% of heap | MEDIUM |
| Single class dominance | > 15% of heap | HIGH |
| Single class growth | > 20% increase | HIGH |
| ThreadLocal dominance | > 10% of heap | HIGH |

### Using `heapdump_analyzer.py leak-check`

Specialized check that compares histogram data against known Minecraft leak signatures. More targeted than `analyze`.

```bash
# Check for known leak patterns
python heapdump_analyzer.py leak-check --jmap-histogram histogram.txt

# From a running process
python heapdump_analyzer.py leak-check --pid 12345

# With total heap for percentage calculations
python heapdump_analyzer.py leak-check --jmap-histogram histogram.txt --total-heap 8589934592
```

**Built-in leak signatures**:

| Class | Leak Type | Threshold | Risk |
|-------|-----------|-----------|------|
| `net.minecraft.world.entity.Entity` | Entity accumulation | > 50,000 instances | HIGH |
| `net.minecraft.world.level.chunk.Chunk` | Chunk loading leak | > 5,000 instances | CRITICAL |
| `net.minecraft.network.Connection` | Connection leak | > 1,000 instances | HIGH |
| `net.minecraft.nbt.CompoundTag` | NBT bloat | > 15% of heap | MEDIUM |
| `net.minecraft.server.level.ServerLevel` | World leak | > 50 instances | CRITICAL |

### Using `heapdump_analyzer.py commands`

Prints platform-specific diagnostic commands for gathering heap data.

```bash
# Linux commands
python heapdump_analyzer.py commands --linux

# Windows commands
python heapdump_analyzer.py commands --windows

# With specific PID
python heapdump_analyzer.py commands --linux --pid 12345
```

---

## Memory Leak Patterns Specific to Minecraft

### Pattern Reference Table

| Pattern | Signs | Detection Method | Fix |
|---------|-------|-------------------|-----|
| **Entity accumulation** | Entity count > 5,000 in a single world, MSPT rising with entity count, Spark `entities` shows high counts | `spark_toolkit.py entities <source>`, `heap` shows `Entity` in top consumers | Set `entity-per-chunk-save-limit`, lower `spawn-limits`, increase despawn ranges, check mob farms |
| **Chunk loading leak** | Chunk count continuously growing, memory rising without players in new areas, `Chunk` objects in heap top 10 | `spark_toolkit.py heap <source>` for Chunk instances, `gc` shows growing old gen | Reduce `view-distance`, set `chunk-unload-delay`, check plugins keeping chunks loaded, use Chunky for pre-gen |
| **Connection leak** | Connection objects growing, Netty thread CPU increasing, players can't reconnect after "already connected" errors | `heapdump_analyzer.py leak-check` for Connection instances, `spark_toolkit.py heap <source> --type-filter "Connection"` | Fix disconnect handler in plugins, ensure Netty channel cleanup, check for missing `PlayerQuitEvent` cleanup |
| **NBT bloat** | `CompoundTag` dominating heap, player data files large, slow world saves | `spark_toolkit.py heap <source> --type-filter "CompoundTag"`, `leak-check` for NBT patterns | Clean up tile entity data, avoid storing large NBT in metadata, limit scoreboard entries |
| **Plugin cache leak** | Static `HashMap` growing, plugin-specific types in heap top 20, cache hit rate near 0% | `spark_toolkit.py plugin-heap <source> --plugin "PluginName"`, compare profiles over time | Add LRU eviction (`LinkedHashMap.removeEldestEntry`), use `Caffeine`/`Guava Cache` with `maximumSize`, add TTL |
| **ThreadLocal leak** | ThreadLocal map entries growing, memory not released after player disconnect | `heapdump_analyzer.py analyze --jmap-histogram`, look for `ThreadLocal$ThreadLocalMap$Entry` | Always call `ThreadLocal.remove()` in finally blocks, avoid ThreadLocal per-player data |
| **Event listener leak** | Event handler list growing, method handles accumulating, listener invocation cost increasing per event | `heapdump_analyzer.py leak-check`, `spark_toolkit.py plugin-profile` for handler counts | Unregister listeners in `onDisable()`, use `HandlerList.unregisterAll()` for plugin, avoid anonymous class listeners |
| **Direct buffer leak** | Direct buffer memory growing, `ByteBuf` not in Java heap but native memory increasing, `OutOfMemoryError: Direct buffer memory` | `jcmd <pid> VM.native_memory`, Netty leak detection (`-Dio.netty.leakDetection.level=PARANOID`) | Always call `ByteBuf.release()` in finally blocks, use `ReferenceCountUtil.release()`, check Netty pipeline handlers |
| **Classloader leak** | Metaspace growing, `Class` instances increasing, OOM in Metaspace after plugin reload | `jcmd <pid> VM.metaspace`, `heapdump_analyzer.py analyze` for classloader patterns | Avoid hot-reloading plugins, restart server instead of `/reload`, ensure static cleanup on disable |
| **RegionFile cache growth** | Region file handles growing, `RegionFile` in heap, `FileInputStream` not closed, slow saves | `heapdump_analyzer.py leak-check`, `lsof <pid> | grep region` on Linux | Ensure chunk unloading works, reduce `region-file-cache-size`, check for plugins preventing chunk unload |

### Detailed Pattern Descriptions

#### Entity Accumulation

Entities spawn but never despawn. Common in mob farms, spawner rooms, or when `entity-per-chunk-save-limit` is not set.

**Detection sequence**:
1. `spark_toolkit.py entities <source>` - shows entity counts by type
2. Check if entity count is proportional to player count (> 500 entities per player is problematic)
3. `spark_toolkit.py heap <source> --type-filter "Entity"` - confirms entity memory impact
4. `heapdump_analyzer.py leak-check --jmap-histogram histogram.txt` - flags entity leak signature

#### Chunk Loading Leak

Chunks are loaded but never unloaded. Causes: plugins forcing chunks to stay loaded, high view-distance, broken chunk GC.

**Detection sequence**:
1. `spark_toolkit.py gc <source>` - shows growing old gen
2. `spark_toolkit.py heap <source> --type-filter "Chunk"` - shows chunk object count
3. Compare chunk count vs expected: `(2 * view_distance + 1)^2 * player_count` is the expected range
4. If chunk count is 2-3x expected, something is preventing unloading

#### Connection Leak

Netty channels or Connection objects not being cleaned up. Often caused by plugins not handling disconnect properly.

**Detection sequence**:
1. `spark_toolkit.py heap <source> --type-filter "Connection"` - shows connection count
2. Connection count should match online player count ± a small margin
3. If connection count >> player count, there's a leak

#### Plugin Cache Leak

A plugin caches data in a static map without eviction. Most common plugin-caused memory leak.

**Detection sequence**:
1. `spark_toolkit.py plugin-heap <source> --plugin "SuspectPlugin"` - shows plugin heap share
2. Compare across multiple profiles - growing = leak
3. `heapdump_analyzer.py analyze --jmap-histogram histogram.txt` - shows `HashMap$Node` dominance

---

## heapdump_analyzer.py Quick Reference

### analyze - Full Histogram Analysis

```bash
# From a jmap histogram file (Linux)
jcmd <pid> GC.class_histogram > histogram.txt
python heapdump_analyzer.py analyze --jmap-histogram histogram.txt

# From a jmap histogram file (Windows)
jcmd <pid> GC.class_histogram > histogram.txt
python heapdump_analyzer.py analyze --jmap-histogram histogram.txt

# With total heap specified (for accurate percentages)
python heapdump_analyzer.py analyze --jmap-histogram histogram.txt --total-heap 8589934592

# Live process analysis (auto-detects PID)
python heapdump_analyzer.py analyze --pid 12345

# Save results
python heapdump_analyzer.py analyze --jmap-histogram histogram.txt -o analysis.json
```

### leak-check - Known Leak Pattern Check

```bash
# Check against Minecraft leak signatures
python heapdump_analyzer.py leak-check --jmap-histogram histogram.txt

# With total heap for percentage calculations
python heapdump_analyzer.py leak-check --jmap-histogram histogram.txt --total-heap 8589934592

# Live process
python heapdump_analyzer.py leak-check --pid 12345
```

### commands - Diagnostic Commands

```bash
# Linux diagnostic commands
python heapdump_analyzer.py commands --linux

# Windows diagnostic commands
python heapdump_analyzer.py commands --windows

# With specific PID (Linux)
python heapdump_analyzer.py commands --linux --pid 12345

# With specific PID (Windows)
python heapdump_analyzer.py commands --windows --pid 12345
```

---

## jstat and jcmd Commands

### jstat Commands for Leak Detection

| Command | Purpose | What to Check |
|---------|---------|---------------|
| `jstat -gc <pid> 1000 10` | GC statistics every 1s, 10 times | Old gen (O) growing, Full GC (FGC) count increasing |
| `jstat -gcutil <pid> 1000 10` | GC as percentages | Old gen % trend, Full GC count |
| `jstat -gccapacity <pid> 1000` | GC capacity by generation | Old gen capacity vs used, metaspace usage |
| `jstat -gcnew <pid> 1000` | Young generation stats | Young gen filling too fast = allocation storm |
| `jstat -gcold <pid> 1000` | Old generation stats | Old gen growth rate, promotion rate |
| `jstat -gcmetacapacity <pid> 1000` | Metaspace capacity | Metaspace growing = classloader leak |
| `jstat -printcompilation <pid> 1` | JIT compilation (less relevant) | Not directly leak-related |

**jstat interpretation for leak detection**:

```
jstat -gcutil <pid> 1000 5

  S0     S1     E      O      M     CCS    YGC   YGCT   FGC  FGCT   GCT
  0.00  45.23  78.12  67.34  95.12  92.45   125   1.234    2   0.456   1.690
  0.00  48.91  82.45  68.12  95.15  92.47   128   1.267    2   0.456   1.723
  0.00  52.34  75.89  69.01  95.18  92.49   132   1.301    2   0.456   1.757
  0.00  55.12  80.23  69.89  95.21  92.51   135   1.334    2   0.456   1.790
  0.00  58.78  77.56  70.56  95.24  92.53   138   1.367    2   0.456   1.823
```

**In this example**: Old gen (O) growing from 67% to 70% in 5 seconds. If this trend continues, it's a leak.

### jcmd Commands for Leak Detection

| Command | Purpose | What to Check |
|---------|---------|---------------|
| `jcmd <pid> GC.heap_info` | Heap summary by generation | Old gen used vs committed vs max |
| `jcmd <pid> GC.class_histogram` | Object count by class (quick, low overhead) | Dominant types, entity/chunk counts |
| `jcmd <pid> GC.heap_dump <file>` | Full heap dump for MAT analysis | Use when leak confirmed, for deep analysis |
| `jcmd <pid> VM.metaspace` | Metaspace usage and limits | Classloader leak, metaspace growth |
| `jcmd <pid> VM.native_memory` | Native memory tracking | Direct buffer usage, native allocations |
| `jcmd <pid> VM.info` | JVM info including flags | Verify GC config, heap settings |
| `jcmd <pid> Thread.print` | Thread dump | ThreadLocal leaks, blocked threads |
| `jcmd <pid> GC.run_finalization` | Run finalizers | Rarely useful, but can clear reference queue |
| `jcmd <pid> VM.command_line` | JVM startup flags | Verify -Xmx, GC flags |

**jcmd workflow for leak confirmation**:

```bash
# Step 1: Check current heap state
jcmd <pid> GC.heap_info

# Step 2: Quick histogram (low overhead, no STW pause)
jcmd <pid> GC.class_histogram > histogram1.txt

# Step 3: Wait 10-30 minutes

# Step 4: Another histogram to compare
jcmd <pid> GC.class_histogram > histogram2.txt

# Step 5: Compare to find growing types
diff histogram1.txt histogram2.txt

# Step 6: If leak confirmed, take full heap dump
jcmd <pid> GC.heap_dump /tmp/heapdump.hprof
```

### jstat Key Columns for Leak Detection

| Column | Full Name | Leak-Relevant Meaning |
|--------|-----------|----------------------|
| **O** | Old space utilization % | Growing = leak or promotion pressure |
| **FGC** | Full GC count | Increasing = memory pressure |
| **FGCT** | Full GC total time | Time spent in Full GC, cumulative |
| **M** | Metaspace utilization % | Growing = classloader leak |
| **YGC** | Young GC count | Increasing rapidly = allocation storm |
| **S0/S1** | Survivor space % | Always full = promotion rate too high |

### Taking a Heap Dump for Deep Analysis

| Method | Command | Overhead | When to Use |
|--------|---------|----------|-------------|
| **jcmd heap dump** | `jcmd <pid> GC.heap_dump /tmp/dump.hprof` | STW pause, disk I/O | Confirmed leak, need deep analysis |
| **jmap histogram** | `jcmd <pid> GC.class_histogram > hist.txt` | Minimal | Quick leak check, low overhead |
| **jmap dump** | `jmap -dump:live,format=b,file=dump.hprof <pid>` | STW + Full GC first | When you need only live objects |
| **JFR event** | JDK Flight Recording with `ObjectAllocationInNewTLAB` | Low | Continuous monitoring of allocation |

**Important**: Heap dumps can be as large as the heap (8GB heap = ~8GB dump). Ensure sufficient disk space.

---

## Memory Leak Detection Workflow

### Step-by-Step: From Suspicion to Root Cause

#### Step 1: Spark Heap Analysis

```bash
python spark_toolkit.py heap <source>
python spark_toolkit.py heap <source> --limit 20
```

**What you're looking for**:
- Which types consume the most heap
- Whether plugin-attributable types are dominant
- Whether Entity, Chunk, or Connection types are unusually large

**Decision**: If heap shows a clear dominant type or plugin, proceed to Step 2 for GC confirmation. If not clear, proceed to Step 2 anyway.

#### Step 2: Spark GC Analysis

```bash
python spark_toolkit.py gc <source>
```

**What you're looking for**:
- Old gen growing monotonically (leak confirmed)
- Full GC count > 0 and growing (memory pressure)
- Full GC recovering < 10% (objects not collectible = true leak)
- Total GC time > 10% of profile time (GC thrashing)

**Decision**: If GC shows leak pattern (old gen growing, Full GC ineffective), proceed to Step 3 for plugin attribution. If GC is normal, the issue may be bloat or high usage rather than a leak.

#### Step 3: Spark Plugin Heap Attribution

```bash
python spark_toolkit.py plugin-heap <source> --plugin "SuspectPlugin"
python spark_toolkit.py plugin-profile <source> --plugin "SuspectPlugin"
```

**What you're looking for**:
- Plugin responsible for > 5% of heap
- Plugin's object count growing over time
- HashMap/ArrayList dominance in plugin's types

**Decision**: If a plugin is identified as the leak source, report to plugin author. If no clear plugin, proceed to Step 4.

#### Step 4: Heap Dump Analysis

```bash
# Take histogram (low overhead)
jcmd <pid> GC.class_histogram > histogram.txt
python heapdump_analyzer.py analyze --jmap-histogram histogram.txt --total-heap <heap_bytes>
python heapdump_analyzer.py leak-check --jmap-histogram histogram.txt --total-heap <heap_bytes>

# If leak confirmed, take full heap dump for MAT
jcmd <pid> GC.heap_dump /tmp/heapdump.hprof
```

**What you're looking for**:
- `analyze`: Top consumers, dominance patterns, leak signatures
- `leak-check`: Known Minecraft leak patterns flagged
- Compare histogram at two time points to identify growing types

**Decision**: Identify the specific type(s) growing. Proceed to Step 5 for deep dive.

#### Step 5: Eclipse MAT Deep Analysis

1. Open `.hprof` in Eclipse MAT
2. Run "Leak Suspects Report" (automated)
3. Run "Dominator Tree" to find biggest object retainers
4. Use "Path to GC Roots" → "exclude weak/soft references" on suspect objects
5. Identify the reference chain keeping objects alive

**What you're looking for**:
- The GC root holding the leak (static field, ThreadLocal, active thread)
- The object that retains the most shallow heap
- The shortest path from GC root to leaked objects

#### Step 6: Identify Root Cause and Fix

| Root Cause Pattern | Fix |
|-------------------|-----|
| Static HashMap growing without bounds | Add eviction (LRU, TTL, maximumSize) |
| ThreadLocal not removed | Call `.remove()` in finally block |
| Event listener not unregistered | Unregister in `onDisable()` |
| Netty ByteBuf not released | Call `release()` or use `SimpleChannelInboundHandler` |
| Classloader not GC'd after plugin reload | Restart server instead of `/reload` |
| Chunk force-loaded by plugin | Remove force-loaded chunks, use `ChunkUnloadEvent` cleanup |
| Player data cached indefinitely | Add TTL or use `WeakHashMap` |
| Entity spawned without despawn condition | Add entity limit, fix spawn rules |
| Collection in singleton growing | Initialize with expected size, add bounds |
| Scheduled task not cancelled on disable | Cancel all tasks in `onDisable()` |

### Quick Decision Tree

```
Server running out of memory?
│
├── Sudden OOM after specific action
│   └── Action likely caused large allocation → Check what triggered it → Fix or limit
│
├── Gradual memory growth over hours/days
│   ├── Heap growing, GC can't recover → Memory leak (follow workflow above)
│   └── Heap growing, GC recovers well → Memory bloat → Reduce cache sizes
│
├── Memory grows with player count, drops when players leave
│   └── Normal scaling → Increase Xmx or optimize per-player usage
│
└── Memory never drops even after players leave
    └── Leak confirmed → Follow full workflow, focus on plugin attribution
```

### Monitoring Checklist

| Check | Command | Frequency | Threshold |
|-------|---------|-----------|-----------|
| Old gen % after Full GC | `jstat -gcutil <pid> 60000` | Every hour during investigation | Should stay < 60% |
| Full GC count | `jstat -gc <pid>` | Every hour | Should be 0 or very low |
| Top heap consumers | `jcmd <pid> GC.class_histogram` | Every 15 min during investigation | Compare across runs |
| Total heap used | `jcmd <pid> GC.heap_info` | Every hour | Should not monotonically increase |
| Metaspace used | `jcmd <pid> VM.metaspace` | Every 30 min during investigation | Should stabilize after startup |
| Spark heap comparison | `spark_toolkit.py heap <source>` | Every 30 min during investigation | Growth > 5% = investigate |