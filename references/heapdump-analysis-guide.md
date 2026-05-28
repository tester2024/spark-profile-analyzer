# Heap Dump Analysis for Minecraft Servers

Systematic approach to collecting, analyzing, and resolving memory issues using Java heap dumps and spark profiler data.

---

## Overview

### What Heap Dumps Are

A heap dump is a snapshot of all objects in the JVM heap at a point in time. It contains every live object: its class, fields, size, and references to other objects. Heap dumps are the definitive tool for diagnosing memory leaks and excessive memory consumption.

| Format | Extension | Content | Typical Size |
|--------|-----------|---------|-------------|
| HPROF binary | `.hprof` | Full object graph with references | 50-200% of Xmx |
| HPROF with `--compress` | `.hprof.gz` | Compressed full dump | 10-30% of Xmx |
| jmap histogram | text | Class → instance count + total size | <1MB |
| Spark heapsummary | text | Aggregated type summary from spark | <100KB |

### When to Take a Heap Dump

| Situation | Action | Priority |
|-----------|--------|----------|
| OOM error in logs | Take dump immediately | CRITICAL |
| Old gen monotonically growing | Take 2 dumps 30min apart | HIGH |
| Heap at 80%+ after Full GC | Take dump for bloat analysis | HIGH |
| Periodic GC pauses causing lag | Take dump during high usage | MEDIUM |
| Memory usage higher than expected | Take dump for baseline | LOW |
| Before/after plugin changes | Take dump for comparison | LOW |

### How Heap Dumps Relate to Spark Data

Spark provides **live** telemetry. Heap dumps provide **deep** object analysis. Use them together:

| Data Source | What It Shows | When to Use |
|-------------|--------------|-------------|
| `/spark gc` | GC frequency, pause times, generation sizes | Detecting GC pressure from memory |
| `/spark heapsummary` | Top types by size/instances (like jmap histogram) | Quick check for obvious bloat |
| `/spark heap` | Aggregated heap info from profiler | Correlating CPU hotspots with memory |
| `/spark plugin-heap <name>` | Memory attributed to a specific plugin | Confirming plugin is responsible |
| jmap histogram | Complete class histogram | Detailed type-level analysis |
| Full .hprof dump | Every object with references | Deep leak investigation |

### When to Use Spark `heap` vs a Full Heap Dump

| Scenario | Use Spark `heap` | Use Full Heap Dump |
|----------|-----------------|---------------------|
| Quick type-level breakdown | Yes | No — overkill |
| Identify which plugin owns memory | Yes (`plugin-heap`) | Possible but tedious in MAT |
| Find reference chain causing leak | No — spark doesn't track refs | Yes — this is what hprof is for |
| Remote analysis (no server access) | Yes — from spark URL | No — need server access |
| Quantifying "how many X objects" | Yes | Yes |
| Diagnosing OOM root cause | No — insufficient detail | Yes — only way to find the leaking reference |
| Minimal server impact | Yes — negligible | No — STW pause for seconds to minutes |
| Comparing before/after | Yes — lightweight enough to run twice | Possible but each dump causes STW pause |

**Rule of thumb**: Start with `/spark heapsummary` and spark_toolkit `heap`. Escalate to jmap histogram. Only use full hprof dumps when you need reference chains (leak suspects).

---

## Collecting Heap Dumps

### Method 1: `/spark heapsummary` (In-Game)

```
/spark heapsummary
```

Lightweight. No file produced. Shows top types by size and instance count. Does NOT pause the server. Use for initial triage.

```
/spark heapsummary --run-gc-before
```

Runs GC first, then captures. Shows only live (post-GC) objects. Better for identifying true leaks since GC-eligible objects are removed.

### Method 2: `spark_toolkit.py heap` (From Spark Data)

```bash
python3 spark_toolkit.py heap https://spark.lucko.me/abc123
python3 spark_toolkit.py heap https://spark.lucko.me/abc123 --plugin "com.example" --limit 20
```

Analyzes heap data embedded in the spark profile. No server access needed. Good for remote analysis.

### Method 3: `heapdump_analyzer.py` (From jmap or Live Process)

```bash
# Connect to running Java process (auto-detects PID)
python3 heapdump_analyzer.py analyze --pid <pid>

# Analyze a saved jmap histogram file
python3 heapdump_analyzer.py analyze --jmap-histogram histogram.txt

# Check against known Minecraft leak patterns
python3 heapdump_analyzer.py leak-check --jmap-histogram histogram.txt

# Show diagnostic commands for your platform
python3 heapdump_analyzer.py commands --linux
python3 heapdump_analyzer.py commands --windows
```

The analyzer auto-detects Minecraft leak signatures, classifies types, and calculates heap percentages.

On Windows, use `python` instead of `python3`:

```cmd
python heapdump_analyzer.py analyze --pid 12345
python heapdump_analyzer.py leak-check --jmap-histogram histogram.txt
python heapdump_analyzer.py commands --windows
```

### Method 4: `jmap -histo:live` (JDK Tool)

```bash
# Linux
jmap -histo:live <pid> | head -50

# Windows
jmap -histo:live <pid> > histogram.txt
```

Shows top 50 classes by heap usage. Fast (pauses 1-5 seconds). No large file produced. Good first step before a full dump.

The `:live` flag triggers a Full GC first, so only reachable objects are counted. Without `:live`, objects awaiting GC are included.

When to use `:live` vs without:
| Variant | What it shows | When to use |
|---------|--------------|------------|
| `-histo:live` | Only reachable objects after Full GC | Identifying leaks (objects that survived GC) |
| `-histo` (no live) | All objects including GC-eligible | Finding allocation hotspots (what's being created) |
| Difference between the two | GC-eligible garbage | Objects in difference = garbage that hasn't been collected yet |

### Method 5: `jmap -dump:format=b,file=heap.hprof <pid>`

```bash
# Linux
jmap -dump:format=b,file=heap.hprof <pid>

# Windows
jmap -dump:format=b,file=heap.hprof <pid>
```

Full binary heap dump. Pauses the JVM for the duration of the dump (can be seconds to minutes depending on heap size). The dump file size is roughly equal to the live heap size.

| Heap Size | Dump Time | File Size |
|-----------|-----------|-----------|
| 4GB | 5-15s | ~3-4GB |
| 8GB | 15-45s | ~6-8GB |
| 16GB | 30-90s | ~12-16GB |
| 32GB | 1-3min | ~24-32GB |

**Warning**: This causes a full STW pause for the entire dump duration. Do not do this on a production server during peak hours unless you accept the downtime.

### Method 6: `jcmd <pid> GC.heap_dump heap.hprof`

```bash
jcmd <pid> GC.heap_dump heap.hprof
```

Same output as jmap but uses the JCMD interface. Preferred on JDK 9+. Same STW pause applies.

### Method 7: Automatic on OOM

Add to JVM startup flags:

```
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/path/to/dumps/
```

The JVM automatically produces a `.hprof` file when an OOM occurs. Essential for post-crash diagnosis. The dump path must have enough free disk space (2x Xmx recommended).

Combine with:

```
-XX:OnOutOfMemoryError="command to execute"
```

For example, to send an alert:

```
-XX:OnOutOfMemoryError="mail -s 'OOM on server' admin@example.com"
```

Or to restart the server:

```
-XX:OnOutOfMemoryError="/usr/bin/systemctl restart minecraft"
```

### Method 8: Spark Heap Dump

```
/spark heapdump
/spark heapdump --compress gzip
```

Produces a `.hprof` file in the server directory. Supports gzip/xz/lzma compression to reduce size. Use `--compress gzip` for production servers (reduces file size by ~70%).

### Method 9: Eclipse MAT and VisualVM

| Tool | Best For | Heap Size Limit | Key Feature |
|------|----------|----------------|-------------|
| Eclipse MAT | Leak hunting, dominator tree | 64GB+ with 2x RAM | Leak Suspects report, OQL queries |
| VisualVM | Quick inspection, GC monitoring | Works well up to ~8GB | Live monitoring, lightweight |
| JXray | Class and reference analysis | Up to 32GB | Reference chain visualization |
| YourKit | Profiling + heap analysis | Any | Integrated CPU + heap profiling |

**MAT Memory Requirements**: To analyze a dump, MAT needs roughly 2x the dump file size in RAM. Analyze a 16GB dump on a machine with at least 32GB RAM. Use `-Xmx24g` when launching MAT for large dumps.

**VisualVM**: Better for live monitoring. Use the "Monitor" tab to watch heap usage in real-time, and "Sampler" tab for allocation profiling. Not as powerful as MAT for dump analysis but much faster to start using.

### Finding the Java PID

**Linux:**

```bash
ps aux | grep java | grep -v grep
# or
jps -l                    # lists all Java processes
pgrep -f "minecraft"      # find by process arguments
```

**Windows:**

```cmd
tasklist /FI "IMAGENAME eq java.exe"
# or
wmic process where "name='java.exe'" get ProcessId,CommandLine
```

---

## Using heapdump_analyzer.py

### Command Reference

| Command | Purpose |
|---------|---------|
| `analyze --pid <pid>` | Connect to running server, run jmap histogram + jstat + jcmd |
| `analyze --jmap-histogram <file>` | Analyze a saved jmap histogram text file |
| `commands --linux` | Show Linux diagnostic commands |
| `commands --windows` | Show Windows diagnostic commands |
| `leak-check --jmap-histogram <file>` | Check histogram against known Minecraft leak patterns |

### analyze Command

```bash
# Linux: Auto-detect Java process
python3 heapdump_analyzer.py analyze

# Linux: Specify PID
python3 heapdump_analyzer.py analyze --pid 12345

# Linux: Analyze a saved histogram file
python3 heapdump_analyzer.py analyze --jmap-histogram histogram.txt

# Linux: Specify total heap for percentage calculations
python3 heapdump_analyzer.py analyze --jmap-histogram histogram.txt --total-heap 8589934592

# Linux: Save output to file
python3 heapdump_analyzer.py analyze --jmap-histogram histogram.txt -o analysis.json
```

```cmd
REM Windows: Specify PID
python heapdump_analyzer.py analyze --pid 12345

REM Windows: Analyze a saved histogram file
python heapdump_analyzer.py analyze --jmap-histogram histogram.txt

REM Windows: Specify total heap for percentage calculations
python heapdump_analyzer.py analyze --jmap-histogram histogram.txt --total-heap 8589934592

REM Windows: Save output to file
python heapdump_analyzer.py analyze --jmap-histogram histogram.txt -o analysis.json
```

Output includes:
- `histogram_analysis`: Top 20 consumers, type breakdown, leak findings
- `gc_utilization`: jstat output (if PID available)
- `heap_info`: jcmd GC.heap_info output (if PID available)
- `diagnostic_commands`: Platform-specific commands for further investigation

### leak-check Command

```bash
# Linux
python3 heapdump_analyzer.py leak-check --jmap-histogram histogram.txt

# Windows
python heapdump_analyzer.py leak-check --jmap-histogram histogram.txt
```

Returns:
- `leak_signatures`: All Minecraft-specific leak patterns with thresholds
- `common_leak_patterns`: Generic Java leak pattern descriptions
- `gc_log_indicators`: GC log-based leak indicators
- `diagnostic_commands`: Platform-specific commands
- `histogram_analysis`: If histogram file is provided, includes analysis results

### commands Command

```bash
# Linux
python3 heapdump_analyzer.py commands --linux

# Windows
python heapdump_analyzer.py commands --windows
```

Prints platform-specific diagnostic commands for jstat, jcmd, jmap, and /proc utilities.

### Leak Signatures Detected

The analyzer checks the histogram against these Minecraft-specific patterns:

| Class | Leak Type | Threshold | Risk |
|-------|----------|-----------|------|
| `net.minecraft.world.entity.Entity` | entity_leak | > 50,000 instances | HIGH |
| `net.minecraft.world.level.chunk.Chunk` | chunk_leak | > 5,000 instances | CRITICAL |
| `net.minecraft.network.Connection` | connection_leak | > 1,000 instances | HIGH |
| `net.minecraft.nbt.CompoundTag` | nbt_bloat | > 15% of heap | MEDIUM |
| `net.minecraft.server.level.ServerLevel` | world_leak | > 50 instances | CRITICAL |
| `java.lang.Thread` | thread_leak | > 500 instances | HIGH |
| `java.util.concurrent.ConcurrentHashMap` | map_leak | > 10% of heap | MEDIUM |
| `java.util.HashMap` | map_bloat | > 15% of heap | MEDIUM |
| `io.netty.buffer.PoolArena` | netty_buffer_leak | > 200 instances | HIGH |
| `io.netty.channel.DefaultChannelPipeline` | netty_pipeline_leak | > 500 instances | HIGH |
| `byte[]` | byte_array_bloat | > 25% of heap | MEDIUM |
| `char[]` | string_bloat | > 25% of heap | LOW |
| `java.lang.String` | string_dominance | > 20% of heap | LOW |

### Type Classification

The analyzer automatically categorizes histogram entries:

| Category | Classes |
|----------|---------|
| byte_arrays | `byte[]` |
| strings | `String`, `char[]` |
| primitive_arrays | `int[]`, `long[]`, `double[]`, `float[]` |
| collections | `HashMap`, `ConcurrentHashMap`, `LinkedHashMap`, `TreeMap` |
| threads | `Thread`, `ThreadPoolExecutor` |
| netty | `io.netty.*` |
| minecraft_server | `net.minecraft.*`, `org.bukkit.*`, `org.spigotmc.*`, `io.papermc.*` |
| entities | Classes containing "entity" + "minecraft"/"bukkit" |
| classloaders | `java.lang.Class`, `java.lang.reflect.*` |

---

## Heap Histogram Analysis

### What `jmap -histo:live <pid>` Shows

```
 num  #instances         #bytes  class name
--------------------------------------------
   1:      1234567    987654321  [B  (byte arrays)
   2:       567890    456789012  java.lang.String
   3:       345678    234567890  net.minecraft.world.level.chunk.Chunk
   4:       234567    123456789  java.util.HashMap
   5:       123456     98765432  net.minecraft.world.entity.Entity
```

Three columns:
- **#instances**: How many objects of this class exist
- **#bytes**: Total heap memory consumed by all instances of this class
- **class name**: Fully qualified class name (or `[B` for `byte[]`, `[C` for `char[]`, etc.)

### Primitive Array Notation

| Notation | Java Type | Common Use in Minecraft |
|----------|-----------|------------------------|
| `[B` | `byte[]` | Packet buffers, NBT data, RegionFile caches, compressed data |
| `[C` | `char[]` | String backing arrays |
| `[I` | `int[]` | Chunk section data, block states, biome arrays |
| `[J` | `long[]` | Chunk section data, heightmaps, mob counts |
| `[D` | `double[]` | Entity position data, physics calculations |
| `[F` | `float[]` | Model data, color arrays |
| `[Ljava.lang.Object;` | `Object[]` | ArrayList backing arrays, varargs |

### What's Normal vs Abnormal for Minecraft

| Class | Normal (10 players) | Normal (50 players) | Normal (100 players) | Abnormal |
|-------|--------------------|--------------------|----------------------|----------|
| `byte[]` | 5-15% of heap | 8-20% of heap | 10-25% of heap | > 30% |
| `String` + `char[]` | 10-20% of heap | 10-20% of heap | 10-20% of heap | > 30% |
| Entity instances | 500-2000 | 2000-5000 | 5000-15000 | > 50000 |
| Chunk instances | 500-2000 | 2000-5000 | 5000-10000 | > 15000 |
| Connection instances | 10-15 | 50-60 | 100-120 | > 500 (no players online) |
| CompoundTag instances | 1000-5000 | 5000-20000 | 20000-50000 | > 100000 |

### Interpreting the Histogram: Decision Table

| Histogram Pattern | What It Means | Next Step |
|-------------------|--------------|-----------|
| `byte[]` is #1 by far (>30%) | Large packet buffers, NBT data, or RegionFile caches | Check RegionFile count, packet sizes, NBT depth |
| `String` + `char[]` dominate (>30% combined) | String bloat from messages, names, config values | Enable `-XX:+UseStringDeduplication` (G1GC only) |
| Specific entity class in top 20 | Entity leak or over-spawning | Check `spark_toolkit entities`, verify spawn limits |
| `HashMap`/`ConcurrentHashMap` in top 10 > expected player count | Plugin cache without eviction | Run `spark_toolkit plugin-heap` for each plugin |
| `Thread` instances > 500 | Thread pool leak in plugin | Check `jcmd <pid> Thread.print` for plugin-named threads |
| `PluginClassLoader` appears multiple times for same plugin | Hot-reload leak | Restart instead of reload; clean up static refs |
| `int[]` or `long[]` dominates | Chunk data bloat | Verify view-distance, check chunk leak |

### The 80/20 Rule

In a typical Minecraft server, the top 20 classes consume 80-90% of the heap. Focus your analysis on the top entries:

```
Top 20 classes → 80-90% of heap
Top 50 classes → 95-98% of heap
Everything else → 2-5% of heap
```

If you see an unexpected class in the top 20, that's your investigation target. Common "unexpected" entries that indicate problems:

| Unexpected Top Entry | Likely Cause |
|---------------------|-------------|
| A plugin's package class in top 20 | Plugin memory leak or bloat |
| `ConcurrentHashMap` with massive instance count | Unbounded plugin cache |
| `java.lang.ref.SoftReference` dominating | Weak/soft reference cache not clearing |
| `java.lang.Thread` with high instance count | Thread pool leak |
| `PluginClassLoader` for removed plugin | Plugin hot-reload leak |

### Comparing Histograms Over Time

Take two histograms 30 minutes apart:

```bash
# Time T1
jmap -histo:live <pid> > histogram_t1.txt

# Wait 30 minutes

# Time T2
jmap -histo:live <pid> > histogram_t2.txt
```

Compare instance counts and bytes. Classes growing monotonically between snapshots indicate a leak. Focus on:

1. Classes where `#instances` grew significantly (> 10% increase)
2. Classes where `#bytes` grew but `#instances` stayed flat (objects getting larger)
3. Classes that appear in T2 but not T1 (new types being allocated)

**Quick comparison script** (Linux):

```bash
# Extract top 30 classes from each, then diff
head -32 histogram_t1.txt > /tmp/h1.txt
head -32 histogram_t2.txt > /tmp/h2.txt
diff /tmp/h1.txt /tmp/h2.txt
```

**Quick comparison script** (Windows PowerShell):

```powershell
$t1 = Get-Content histogram_t1.txt | Select-Object -First 32
$t2 = Get-Content histogram_t2.txt | Select-Object -First 32
Compare-Object $t1 $t2
```

---

## Minecraft-Specific Memory Patterns

### Normal Heap Composition

A healthy Paper server with 20 players, 6 view distance, 4 simulation distance on a 10GB heap:

| Category | % of Heap | Typical MB | Notes |
|----------|----------|-----------|-------|
| Entity objects | 5-15% | 500-1500 | Includes all mobs, items, vehicles |
| Chunk data | 15-25% | 1500-2500 | Sections, block states, biome data |
| Player data | 2-5% | 200-500 | Per-player state, inventory, position |
| NBT data | 5-10% | 500-1000 | CompoundTag objects everywhere |
| String/char[] | 10-20% | 1000-2000 | Names, messages, config values |
| byte[] | 10-20% | 1000-2000 | Packet buffers, serialization, RegionFile |
| Collections (Maps, Lists) | 5-10% | 500-1000 | HashMap, ArrayList, ConcurrentHashMap |
| Netty buffers/channels | 3-8% | 300-800 | Per-connection network buffers |
| Plugin data | 2-10% | 200-1000 | Plugin caches, data stores |
| JVM overhead | 5-10% | 500-1000 | Class metadata, thread stacks, JNI |

### Abnormal Patterns and Their Causes

| Abnormal Pattern | Likely Cause | Severity |
|-----------------|-------------|----------|
| Entity > 30% of heap | Mob farm, spawn limits too high, entity leak | HIGH |
| Chunks > 35% of heap | View distance too high, chunk leak | HIGH |
| Strings > 30% of heap | Chat log storage, unbounded string cache | MEDIUM |
| byte[] > 35% of heap | Packet leak, RegionFile cache, compressed data | HIGH |
| Single plugin > 15% of heap | Plugin memory leak or bloat | HIGH |
| Collections > 20% of heap | Unbounded caches, missing eviction | MEDIUM |
| Netty > 15% of heap | Connection leak, direct buffer leak | HIGH |
| ClassLoader > 5% of heap | Hot-reload leak | CRITICAL |

### Entity Heap Dominance

**Symptom**: Entity classes consume > 30% of heap. `net.minecraft.world.entity.Entity` or specific entity subclasses appear in top 10.

**Diagnosis**: Too many entities per loaded chunk.

| Entity Count (active) | Heap Impact | Severity |
|----------------------|-------------|----------|
| < 1000 | < 200MB | Normal |
| 1000-3000 | 200-600MB | Acceptable |
| 3000-5000 | 600MB-1GB | Warning |
| 5000-10000 | 1-2GB | High |
| > 10000 | > 2GB | Critical - investigate |

**Per-entity memory estimates**:

| Entity Type | Base Memory | With AI/Pathfinding | With Equipment/Effects |
|-------------|------------|---------------------|----------------------|
| Item (dropped) | 200-400 bytes | 200-400 bytes | N/A |
| Zombie | 2-4KB | 4-12KB | 8-20KB |
| Skeleton | 2-4KB | 4-12KB | 8-20KB |
| Villager | 4-8KB | 8-20KB | 16-40KB |
| Creeper | 2-4KB | 4-12KB | 8-20KB |
| Hopper Minecart | 4-8KB | 4-8KB | 8-16KB |
| Ender Dragon | 20-40KB | 40-100KB | N/A |

**Fixes**:

| Fix | Config Location | Typical Reduction |
|-----|-----------------|-------------------|
| Reduce spawn-limits | bukkit.yml | 30-60% fewer hostile mobs |
| Per-chunk entity limits | paper-world.yml `entity-per-chunk-save-limit` | Hard cap per chunk type |
| Increase despawn ranges | paper-world.yml `despawn-ranges` | Faster natural despawn |
| Reduce activation range | spigot.yml `entity-activation-range` | Less per-entity CPU/Memory |
| Merge dropped items | spigot.yml `merge-radius.item` | Fewer item entities |

### Chunk Leak

**Symptom**: Chunk instance count far exceeds expected count based on player count and view distance. `net.minecraft.world.level.chunk.Chunk` in top 10.

**Expected chunks per player**: `[(view_distance + 2) × 2 + 1]² / shared_factor`

| View Distance | Chunks per Player | For 20 Players (some sharing) |
|---------------|-------------------|-------------------------------|
| 4 | 169 | ~2000-2500 |
| 6 | 289 | ~3500-4500 |
| 8 | 441 | ~5500-7000 |
| 10 | 625 | ~8000-10000 |

**Signs of a chunk leak**:
- Chunk count keeps growing even when players leave
- Chunk count doesn't decrease after reducing view-distance
- `RegionFile` instances growing without bound
- Old gen growing steadily with no corresponding player activity

**Fixes**:

| Fix | Config/Command |
|-----|---------------|
| Reduce view-distance | `server.properties` view-distance |
| Reduce simulation-distance | `server.properties` simulation-distance |
| Pre-generate worlds | Chunky plugin |
| Force unload idle chunks | Paper `delay-chunk-unloads-by` = 0 (default) |
| Check for plugins loading chunks | Search spark for `loadChunk`, `getChunkAt` |

### Connection Leak

**Symptom**: `net.minecraft.network.Connection` or `io.netty.channel.*` instances far exceed online player count.

| Online Players | Normal Connections | Warning | Critical |
|---------------|-------------------|---------|----------|
| 0 | 0-10 (keep-alive) | 50+ | 200+ |
| 20 | 20-30 | 100+ | 500+ |
| 100 | 100-120 | 300+ | 1000+ |

**Diagnosis**: Check spark for `Connection` instances. If count doesn't drop when players disconnect, it's a leak.

**Common causes**:
1. Plugin not cleaning up on `PlayerQuitEvent`
2. Netty channel not released on disconnect
3. Proxy (BungeeCord/Velocity) forwarding connections not closing
4. Login timeout connections not cleaned up

**Fix**: Check `spark plugin-heap` for the plugin holding Connection references. Look for plugins that register `PlayerJoinEvent` but not `PlayerQuitEvent`.

### NBT Bloat

**Symptom**: `net.minecraft.nbt.CompoundTag` instances consume > 15% of heap.

**Sources of NBT memory**:

| Source | Memory per Instance | Typical Count | Total Impact |
|--------|-------------------|---------------|-------------|
| Tile Entity (Block Entity) NBT | 1-10KB each | 1000-50000 | 10-500MB |
| Entity NBT | 500 bytes - 5KB each | 1000-10000 | 0.5-50MB |
| Player data NBT | 10-50KB each | 20-100 | 0.2-5MB |
| Saved data | 100KB-10MB each | 5-20 | 0.5-200MB |
| Region file header cache | 4-8KB per region | 100-1000 | 0.4-8MB |

**Fixes**:

| Fix | Impact |
|-----|--------|
| `tile-entity-skip-list` in paper-world.yml | Skip ticking tile entities that don't need it |
| `entity-per-chunk-save-limit` | Cap entities saved per chunk |
| Reduce tile entity count | Avoid builds with thousands of hoppers, chests, signs |
| Limit hoppers per chunk | Server-level or via plugin |

### String Bloat

**Symptom**: `java.lang.String` + `char[]` together consume > 30% of heap. Thousands of duplicate strings.

**Common sources in Minecraft servers**:
- Player names stored repeatedly in different data structures
- Item/block names duplicated across inventories
- Chat messages retained in plugin history buffers
- Configuration values stored as strings
- Permission names checked frequently

**Quick check for string duplication**:

```bash
# In Eclipse MAT OQL:
SELECT COUNT(*), c.value FROM java.lang.String c GROUP BY c.value HAVING COUNT(*) > 100 ORDER BY COUNT(*) DESC
```

**Fix**: Add `-XX:+UseStringDeduplication` to JVM flags (G1GC only). See String Deduplication in Fixing section.

### Netty Buffer Memory

**Symptom**: `io.netty.buffer.PoolArena` or `java.nio.DirectByteBuffer` instances growing steadily. Direct memory (`-XX:MaxDirectMemorySize`) approaching limit.

| Connection Scale | Normal Direct Memory | Warning | Critical |
|-----------------|---------------------|---------|----------|
| 20 players | 16-64MB | 128MB | 256MB |
| 100 players | 64-256MB | 512MB | 1GB |
| 500 players | 256MB-1GB | 2GB | 4GB |

**Key insight**: Netty uses both heap and direct ByteBuf. Direct buffers don't show in normal heap histograms — you need `jcmd <pid> VM.native_memory summary` or `-XX:MaxDirectMemorySize` monitoring.

---

## Memory Leak vs Memory Bloat

### Decision Tree

```
Is old gen growing monotonically over time?
│
├── NO → Memory is stable. Check if usage is acceptable.
│   └── Usage > 80% after Full GC? → Increase heap or reduce bloat.
│
└── YES → Old gen grows without bound.
    │
    ├── Run Full GC (jcmd <pid> GC.run)
    │   │
    │   ├── After Full GC, old gen drops significantly (> 30% freed)
    │   │   └── It's BLOAT. Legitimate objects consuming too much memory.
    │   │       └── Reduce object sizes, add caches with eviction,
    │   │           reduce view-distance, entity limits.
    │   │
    │   └── After Full GC, old gen barely changes (< 10% freed)
    │       └── It's a LEAK. Objects that should be GC'd but aren't.
    │           └── Take heap dump → Eclipse MAT → Leak Suspects
    │           └── Check for static collections, ThreadLocals, listeners
    │
    └── Check metaspace: Is it also growing?
        ├── YES → ClassLoader leak (plugin hot-reload)
        │   └── Search for PluginClassLoader instances in heap dump
        └── NO → Object leak in Java heap
            └── Search for largest retained sets in MAT
```

### Key Distinction

| Aspect | Memory Leak | Memory Bloat |
|---------|------------|-------------|
| Definition | Objects that should be GC'd but can't be reached for collection | Legitimate objects consuming excessive memory |
| Heap behavior | Grows monotonically, never stabilizes | Grows then stabilizes at a high level |
| After Full GC | Old gen barely drops (< 10% freed) | Old gen drops, then fills back up |
| Long-term | OOM inevitable | Server slow but doesn't crash |
| Fix | Find and remove the reference chain | Reduce data sizes, add eviction, tune configs |
| MAT clue | "Leak Suspects" report finds dominators | No single dominator - many small contributors |

### Testing: Leak vs Bloat

1. Take baseline: `jstat -gcutil <pid> 5000 12` (1 minute of samples)
2. Trigger Full GC: `jcmd <pid> GC.run`
3. Take post-GC: `jstat -gcutil <pid> 5000 12`
4. Wait 30 minutes
5. Take post-usage: `jstat -gcutil <pid> 5000 12`
6. Compare old gen (OU column) across all three

| Observation | Diagnosis |
|-------------|-----------|
| Old gen drops 40% after GC, stays low | Bloat (lots of temporary objects) |
| Old gen drops 40% after GC, refills to same level | Bloat (steady-state usage is high) |
| Old gen drops 5% after GC | Leak (objects are held by strong references) |
| Old gen drops 40% then grows beyond previous level | Active leak (new leak sources) |

---

## Common Leak Patterns in Minecraft Servers

### 1. Static Collection Leaks

**Pattern**: Plugin stores data in static Maps/Lists that never get cleared.

**Heap signature**: Large `HashMap`, `ConcurrentHashMap`, or `ArrayList` instances in a plugin's package.

**Detection**:
```sql
-- In Eclipse MAT OQL:
SELECT * FROM java.util.HashMap WHERE toString(refs).contains("com.yourplugin")
```

Or in jmap histogram:
```
# Look for your plugin's package name in class names
jmap -histo:live <pid> | grep "com.yourplugin"
```

**Common forms**:
- `private static final Map<UUID, PlayerData> CACHE` that grows on join but never removes entries on quit
- `private static final List<String> LOG` that appends every event
- `ConcurrentHashMap` used as a "cache" with no maximum size or TTL

**Fix**: Use Caffeine or Guava Cache with `maximumSize()` and `expireAfterWrite()`.

```java
// BAD
private static final Map<UUID, PlayerData> cache = new HashMap<>();

// GOOD
private static final Cache<UUID, PlayerData> cache = Caffeine.newBuilder()
    .maximumSize(10_000)
    .expireAfterWrite(Duration.ofMinutes(30))
    .build();
```

**Detection threshold**: If a static collection has > 2× the online player count entries for player data, or > 100K entries for any other data, investigate eviction.

### 2. ThreadLocal Leaks

**Pattern**: ThreadLocal values set in thread pool threads but never removed. Each thread retains its own copy permanently.

**Heap signature**: `ThreadLocal$ThreadLocalMap` entries with large values. Many `Thread` instances from plugin thread pools.

**Detection**:
```
# In MAT, search for ThreadLocal$ThreadLocalMap
# Check thread count: jcmd <pid> Thread.print
# If thread count grows over time, suspect ThreadLocal or thread pool leak
```

**Common in**: Bukkit plugins that create `ScheduledExecutorService` or `CompletableFuture` with custom ThreadLocals, or that use ThreadLocal for per-player context in async tasks.

**Fix**: Always call `ThreadLocal.remove()` in a `finally` block. Custom thread pools should clean up in `afterExecute()`.

```java
// BAD
private static final ThreadLocal<SomeContext> CTX = ThreadLocal.withInitial(SomeContext::new);
// Never calls CTX.remove()

// GOOD
private static final ThreadLocal<SomeContext> CTX = ThreadLocal.withInitial(SomeContext::new);

public void process() {
    try {
        CTX.set(new SomeContext());
        // ... do work
    } finally {
        CTX.remove();
    }
}
```

### 3. Listener Leaks

**Pattern**: Plugin registers event listeners but doesn't unregister on disable. After plugin reload, old listener objects (with references to old ClassLoader) accumulate.

**Heap signature**: Multiple `PluginClassLoader` instances for the same plugin. `EventExecutor` objects referencing unloaded classes.

**Detection**:
```sql
-- In MAT OQL:
SELECT * FROM org.bukkit.plugin.java.PluginClassLoader WHERE toString(refs).contains("MyPlugin")
-- Multiple instances = leak from hot-reload
```

Or via jcmd:
```bash
jcmd <pid> GC.class_histogram | grep PluginClassLoader
# If you see multiple PluginClassLoader instances for the same plugin, it's a leak
```

**Fix**:
1. Always unregister listeners in `onDisable()`
2. Avoid plugin hot-reload in production. Use full restarts.
3. If using Plugman/etc., accept that some leaks are inevitable on reload.

```java
// GOOD: Proper listener cleanup
public class MyPlugin extends JavaPlugin {
    private Listener myListener;

    @Override
    public void onEnable() {
        myListener = new MyListener();
        getServer().getPluginManager().registerEvents(myListener, this);
    }

    @Override
    public void onDisable() {
        HandlerList.unregisterAll(myListener);
        // Or: HandlerList.unregisterAll(this); // unregisters all this plugin's listeners
    }
}
```

**Severity**: Each hot-reload can leak 5-50MB depending on plugin size. After 10 reloads, expect 50-500MB leaked per plugin. Always restart instead of reload for memory-sensitive servers.

### 4. Cache Without Eviction

**Pattern**: Plugin uses `HashMap`, `ConcurrentHashMap`, or `LinkedHashMap` as a cache without size limits or expiration. Grows indefinitely as new entries are added.

**Heap signature**: Large `HashMap` or `ConcurrentHashMap` with entries far exceeding expected player/data count.

**Scale thresholds**:

| Cache Type | Warning Size | Critical Size |
|-----------|-------------|---------------|
| Player data cache (per player) | > 2× online players | > 5× online players |
| Block location cache | > 100K entries | > 1M entries |
| String/name cache | > 50K entries | > 500K entries |
| Computation result cache | > 10K entries | > 100K entries |

**Fix**: Replace with Caffeine or Guava Cache:

```java
// BAD: Unbounded
Map<String, ExpensiveResult> cache = new ConcurrentHashMap<>();

// GOOD: Bounded with expiry
Cache<String, ExpensiveResult> cache = Caffeine.newBuilder()
    .maximumSize(10_000)
    .expireAfterAccess(Duration.ofMinutes(10))
    .build();
```

**MAT detection**: Find the largest HashMap/ConcurrentHashMap instances by retained size:

```sql
-- In MAT OQL:
SELECT * FROM java.util.concurrent.ConcurrentHashMap c WHERE c.@retainedHeapSize > 1048576
-- Finds all ConcurrentHashMap instances retaining > 1MB
```

### 5. Reference Queue Overflow

**Pattern**: `SoftReference` or `WeakReference` objects in a cache, but the reference queue is never drained. Under moderate memory pressure, SoftReferences keep objects alive too long.

**Heap signature**: High count of `java.lang.ref.SoftReference` instances. Cache appears to grow even with "soft" references.

**Detection**: Count `SoftReference` vs `WeakReference` in histogram. A high SoftReference count means the JVM isn't clearing them because it hasn't felt enough pressure.

**How to check**:

```bash
# Count SoftReference instances
jmap -histo:live <pid> | grep "java.lang.ref.SoftReference"

# If count is > 100K, the cache is not being cleared effectively
```

**Impact**:

| SoftReference Count | Diagnosis |
|--------------------|-----------|
| < 10K | Normal - GC managing fine |
| 10K-100K | Moderate - cache entries surviving longer than expected |
| > 100K | Problem - significant memory held by soft references |
| > 1M | Critical - soft references dominating heap behavior |

**Fix**:
1. Switch from `SoftReference` to `WeakReference` for actively managed caches.
2. Set `-XX:SoftRefLRUPolicyMSPerMB=1000` (default is 1000ms/MB, lower = more aggressive clearing).
3. Use Caffeine with `weakKeys()` or `weakValues()` instead of manual reference-based caches.

### 6. ClassLoader Leaks

**Pattern**: Plugin ClassLoader persists after plugin unload. Holds all plugin classes, static fields, and metadata. Common with plugin managers that support hot-reload.

**Heap signature**: Multiple `URLClassLoader` or `PluginClassLoader` instances for the same plugin name. Metaspace growing over time.

**Detection**:
```bash
# Check metaspace growth
jstat -gcmetacapacity <pid> 5000 10
# If MC (metaspace capacity) keeps growing, suspect ClassLoader leak
```

**In MAT**: Search for the plugin's package in the ClassLoader histogram. If you see classes from an "unloaded" plugin, the ClassLoader is leaked.

**Metaspace growth thresholds**:

| Metaspace Used | Diagnosis |
|---------------|-----------|
| < 100MB | Normal |
| 100-200MB | Check if growing - could be plugin load |
| > 200MB | Likely ClassLoader leak or excessive dynamic class generation |

**Fix**:
1. Never use plugin hot-reload in production. Always do full restarts.
2. Ensure plugins clean up static references, threads, and listeners in `onDisable()`.
3. Add `-XX:MetaspaceSize=256m -XX:MaxMetaspaceSize=512m` to cap growth.

**Each hot-reload can leak**:
- The entire plugin's class data (1-50MB per reload)
- All static fields (variable)
- All thread pools (variable, 1-10MB per thread pool)
- After 5 reloads of a 10MB plugin: ~50-250MB leaked

### 7. Direct Buffer Leaks (Netty ByteBuf)

**Pattern**: Netty ByteBuf objects not being released after use. Common in custom packet handlers or network interceptors in plugins.

**Heap signature**: `io.netty.buffer.PoolArena$DirectArena` instances growing. `java.nio.DirectByteBuffer` count increasing.

**Detection**:
```bash
# Check direct memory
jcmd <pid> VM.native_memory summary
# Look for "Internal" category growing
```

**Netty leak detection** (add to startup flags):
```
-Dio.netty.leakDetection.level=PARANOID
```

This logs a warning whenever a ByteBuf is GC'd without being released. Will significantly hurt performance—only use for debugging.

| Detection Level | Performance Impact | When to Use |
|----------------|-------------------|-------------|
| DISABLED | None | Production |
| SIMPLE | ~1% overhead | Suspected leak, can tolerate minor overhead |
| ADVANCED | ~5% overhead | Active leak investigation |
| PARANOID | ~20% overhead | Confirming a leak during controlled test |

**Fix**: Ensure ByteBuf.release() is called in all code paths:

```java
// BAD: ByteBuf not released
ByteBuf buf = ...;
channel.writeAndFlush(buf);
// if writeAndFlush fails, buf leaks

// GOOD: Release in all paths
ByteBuf buf = ...;
try {
    channel.writeAndFlush(buf).addListener(ChannelFutureListener.CLOSE_ON_FAILURE);
} catch (Exception e) {
    buf.release();
}
```

**Direct memory limits**: Add `-XX:MaxDirectMemorySize=256M` (or appropriate value) if Netty is consuming too much direct memory. Default is equal to Xmx.

### 8. Region File Cache Growth

**Pattern**: Minecraft caches RegionFile objects for loaded regions. In high view-distance or world exploration scenarios, this cache can grow large.

**Heap signature**: `net.minecraft.world.level.chunk.storage.RegionFile` instances growing steadily.

**Normal ranges**:

| Scenario | RegionFile Objects | Memory Impact |
|----------|-------------------|---------------|
| Small world (1k×1k blocks) | 1-10 | < 10MB |
| Server with 6 view distance | 50-200 | 10-50MB |
| Server with 10+ view distance | 200-1000 | 50-500MB |
| Anarchy/exploration server | 1000+ | 500MB+ |

**Fixes**:
1. Reduce view-distance
2. Pre-generate and set world border
3. Monitor `paper-global.yml` chunk auto-save settings
4. Check for plugins calling `getChunkAt()` without proper cleanup

**Detecting region file bloat**:
```bash
# Count region files on disk (Linux)
find /path/to/world/region/ -name "*.mca" | wc -l

# Count region files on disk (Windows PowerShell)
(Get-ChildItem "G:\server\world\region\*.mca").Count

# Compare with active RegionFile objects in heap
jmap -histo:live <pid> | grep RegionFile
```

If the heap has significantly more RegionFile objects than `.mca` files on disk, RegionFiles are not being released properly.

---

## GC Log Indicators

### Old Gen Monotonic Growth

The most reliable indicator of a memory leak.

**Detection**:

```bash
# Take 3 measurements 5 minutes apart
jstat -gc <pid> 300000 3
# Look at OU (old gen used) column - if it grows each sample, it's a leak
```

**Interpretation**:

| OU Growth Rate | Severity | Diagnosis |
|---------------|----------|-----------|
| < 1MB/min | Normal | Old gen absorbing long-lived objects |
| 1-5MB/min | Low leak | Minor leak, will take hours to fill |
| 5-20MB/min | Moderate leak | Active leak, will fill heap in hours |
| 20-100MB/min | Fast leak | Serious leak, OOM in minutes |
| > 100MB/min | Critical leak | OOM imminent, take action NOW |

### Full GC Frees Little

A Full GC should reclaim at least 20-30% of old gen in a healthy server. If it reclaims < 10%, objects are permanently held.

**Detection**:

```bash
# Before Full GC
jcmd <pid> GC.heap_info
# Note: Old generation: used = X MB

# Trigger Full GC
jcmd <pid> GC.run

# After Full GC
jcmd <pid> GC.heap_info
# Note: Old generation: used = Y MB

# Calculate: (X - Y) / X * 100 = % freed
```

| % Freed by Full GC | Diagnosis |
|-------------------|-----------|
| > 30% | Healthy - old gen has reclaimable objects |
| 10-30% | Warning - most objects are pinned |
| < 10% | Leak - objects cannot be collected |
| < 5% | Critical leak - nearly everything is pinned |

### Metaspace Growth

Growing metaspace indicates ClassLoader leaks or excessive dynamic class generation.

**Detection**:

```bash
# Linux
jcmd <pid> VM.metaspace
# or
jstat -gcmetacapacity <pid> 5000 10

# Windows
jcmd <pid> VM.metaspace
# or
jstat -gcmetacapacity <pid> 5000 10
```

| Metaspace Metric | Healthy | Warning | Critical |
|-----------------|---------|---------|----------|
| Used | < 100MB | 100-200MB | > 200MB |
| Growth rate | Stable | < 1MB/hour | > 1MB/hour |
| Capacity growth | Stable | Growing slowly | Growing continuously |

**Common causes**:
- Plugin hot-reload (each reload allocates new ClassLoader + classes)
- Dynamic proxy generation (plugins using cglib, ByteBuddy)
- Groovy/JavaScript scripting engines in plugins
- Each hot-reload: adds 1-50MB to metaspace, never reclaimed

### Allocation Rate Increase

Rising young gen fill rate means the application is allocating more objects over time. Often accompanies a leak.

**Detection**:

```bash
# Measure young gen collection frequency
jstat -gcnew <pid> 1000 30
# If YGC (young GC count) increases faster over 30 seconds, allocation rate is rising
```

| Young GC Frequency | Allocation Rate | Impact |
|-------------------|----------------|--------|
| Every 2-5s | < 200 MB/s | Normal |
| Every 1-2s | 200-500 MB/s | Moderate - watch for growing caches |
| Every 0.5-1s | 500 MB/s - 1 GB/s | High - investigate allocation hotspots |
| Multiple/second | > 1 GB/s | Critical - likely active leak or severe bloat |

### How to Check Each Indicator with jstat/jcmd

**Old gen usage (OU)**:
```bash
jstat -gc <pid> 1000 5
# OU column = old gen used
# OC column = old gen capacity
# Compare OU across samples to see growth
```

**GC utilization percentages**:
```bash
jstat -gcutil <pid> 1000 5
# O column = old gen utilization %
# F column = Full GC count (should be 0 or near 0)
```

**Metaspace**:
```bash
jstat -gcmetacapacity <pid> 1000 5
# MCMN/MCMX/MC columns = metaspace min/max/current
```

**Young gen fill rate**:
```bash
jstat -gcnew <pid> 1000 10
# Count YGC over time, calculate collections per second
# Compare Eden space (E) fill rate
```

**Heap summary**:
```bash
jcmd <pid> GC.heap_info
# Comprehensive heap breakdown including generations
```

---

## Diagnostic Commands Reference

### Linux Commands

| Command | Purpose |
|---------|---------|
| `ps aux \| grep java \| grep -v grep` | Find Java process |
| `jps -l` | List all Java processes |
| `pgrep -f "minecraft"` | Find by process arguments |
| `jstat -gc <pid> 1000 5` | GC statistics (5 samples, 1s apart) |
| `jstat -gcutil <pid> 1000 5` | GC utilization percentages |
| `jstat -gcnew <pid> 1000 5` | Young generation details |
| `jstat -gcold <pid> 1000 5` | Old generation details |
| `jstat -gcmetacapacity <pid> 1000 5` | Metaspace capacity |
| `jmap -heap <pid>` | Heap info (generational breakdown) |
| `jmap -histo:live <pid> \| head -50` | Top 50 heap consumers (after Full GC) |
| `jmap -dump:format=b,file=heapdump.hprof <pid>` | Full heap dump (STW pause!) |
| `jcmd <pid> GC.heap_info` | Comprehensive heap info |
| `jcmd <pid> GC.class_histogram \| head -50` | Top 50 classes by instance count |
| `jcmd <pid> GC.run` | Trigger Full GC |
| `jcmd <pid> GC.run_finalization` | Run finalizers |
| `jcmd <pid> Thread.print` | Thread dump |
| `jcmd <pid> VM.info` | JVM info |
| `jcmd <pid> VM.flags` | All JVM flags |
| `jcmd <pid> VM.native_memory summary` | Native memory tracking |
| `cat /proc/<pid>/status \| grep -E 'VmRSS\|VmSize\|VmPeak'` | Process memory from /proc |
| `ls /proc/<pid>/fd \| wc -l` | Count open file descriptors |
| `cat /proc/<pid>/limits \| grep "open files"` | Check FD limit |

### Windows Commands

| Command | Purpose |
|---------|---------|
| `tasklist /FI "IMAGENAME eq java.exe"` | Find Java process |
| `wmic process where "name='java.exe'" get ProcessId,CommandLine` | Find by command line |
| `jstat -gc <pid> 1000 5` | GC statistics (5 samples, 1s apart) |
| `jstat -gcutil <pid> 1000 5` | GC utilization percentages |
| `jstat -gcnew <pid> 1000 5` | Young generation details |
| `jstat -gcold <pid> 1000 5` | Old generation details |
| `jstat -gcmetacapacity <pid> 1000 5` | Metaspace capacity |
| `jmap -heap <pid>` | Heap info (generational breakdown) |
| `jmap -histo:live <pid> > histogram.txt` | Top heap consumers (saved to file) |
| `jmap -dump:format=b,file=heapdump.hprof <pid>` | Full heap dump (STW pause!) |
| `jcmd <pid> GC.heap_info` | Comprehensive heap info |
| `jcmd <pid> GC.class_histogram` | Class histogram |
| `jcmd <pid> GC.run` | Trigger Full GC |
| `jcmd <pid> Thread.print` | Thread dump |
| `jcmd <pid> VM.info` | JVM info |
| `jcmd <pid> VM.flags` | All JVM flags |

### Enable Native Memory Tracking

Add to JVM flags:
```
-XX:NativeMemoryTracking=summary
```

This enables `jcmd <pid> VM.native_memory summary` to show native memory breakdown (heap, metaspace, threads, direct buffers, etc.). Has ~5-10% performance overhead—use for diagnosis, not production monitoring.

---

## Correlating with Spark Data

### Using `spark heap` + `heapdump_analyzer` Together

**Step 1**: Get spark heap data:
```bash
python3 spark_toolkit.py heap https://spark.lucko.me/abc123
```
This shows top heap consumers and type breakdown from the spark profile.

**Step 2**: Get detailed histogram from the server:
```bash
python3 heapdump_analyzer.py analyze --pid <pid>
```
Or from a saved histogram file:
```bash
python3 heapdump_analyzer.py analyze --jmap-histogram histogram.txt
```

**Step 3**: Cross-reference:
- Spark `heap` shows which types consume the most memory
- `heapdump_analyzer` checks against Minecraft-specific leak thresholds
- Combine to identify if a type is within normal range or needs investigation

### Using `plugin-heap <name>` to Attribute Memory

```bash
python3 spark_toolkit.py plugin-heap https://spark.lucko.me/abc123 --plugin "Essentials"
```

This shows heap memory attributed to a specific plugin. Use it to:
1. Confirm a suspected plugin is responsible for memory pressure
2. Get concrete numbers for "plugin X is using Y% of heap"
3. Compare plugin heap usage before and after config changes

Output includes severity assessment:

| Assessment | % of Heap | Action |
|------------|----------|--------|
| LOW | < 5% | No concern |
| WARNING | 5-10% | Monitor |
| CRITICAL | > 10% | Investigate immediately |

### Using `gc` Command Data

```bash
python3 spark_toolkit.py gc https://spark.lucko.me/abc123
```

This shows GC statistics from the spark profile. Key correlations:

| GC Finding | Memory Implication | Next Step |
|-----------|-------------------|-----------|
| G1 Full GC occurring | Old gen is full | Take heap dump, check for leaks |
| Young GC frequency increasing | Allocation rate rising | Check for growing caches |
| ZGC allocation stalls | Heap nearly full | Increase heap or reduce allocation |
| GC overhead > 5% | GC consuming too much CPU | Balance heap size and GC algorithm |
| Old gen > 70% after Full GC | Leak or too-small heap | Run leak check with heapdump_analyzer |

### Correlation Workflow

| What You See in Spark | Correlate With | What It Means |
|----------------------|----------------|---------------|
| High GC overhead (spark `gc`) | Old gen growing (jstat) | Memory pressure causing GC thrashing |
| Specific plugin in `plugin-heap` | That plugin's types in jmap histogram | Plugin is responsible for memory bloat |
| Many entities in `entities` | Entity classes in top 20 jmap | Entity count consuming heap |
| Frequent young GC (`gc`) | High `byte[]` in heap histogram | High allocation rate from packet/NBT churn |
| Old gen not freeing (`gc`) | Dominating object in MAT dominator tree | Memory leak with strong reference chain |

### Cross-Referencing `entities` Command Data

```bash
python3 spark_toolkit.py entities https://spark.lucko.me/abc123
```

This shows entity counts by type and world. Use to correlate with heap findings:

| entities Finding | Likely Heap Finding | Fix |
|-----------------|---------------------|-----|
| > 10,000 entities total | Entity objects in top 20 heap classes | Reduce spawn-limits, increase despawn |
| > 100 entities in single chunk | High per-chunk memory | Entity per-chunk limits |
| Many dropped items | Large `EntityItem` heap usage | Increase `merge-radius.item` |
| Many villagers | High entity heap per-object | Reduce villager count, nerf AI |
| Growing entity count over time | Entity leak | Check for entities not being despawned |

---

## Eclipse MAT Quick Reference

### Installing MAT

1. Download from https://eclipse.dev/mat/
2. For large heaps (> 4GB), edit `MemoryAnalyzer.ini` and set `-Xmx4g` (or more, up to 2x dump size)
3. On JDK 17+, add `--add-modules=java.se.saa` to the ini file if MAT fails to start

**For very large heaps (32GB+):**
```
-Xmx24g
-XX:+UseG1GC
-XX:MaxGCPauseMillis=200
```

### Loading .hprof Files

1. File → Open Heap Dump → select `.hprof` file
2. First load creates index files (can take 10-30 minutes for large dumps)
3. MAT will auto-run the Leak Suspects report
4. Subsequent loads use cached indices and are faster

### Key Reports

#### 1. Leak Suspects Report (Start Here)

Auto-generated on load. Identifies objects that retain the most memory via their reference chains.

**What to look for**:
- Objects retaining > 5% of heap
- "Problem Suspect" entries with short description
- Click "Details" to see the shortest path to the GC root

#### 2. Top Components Report

Shows which classes consume the most memory. Similar to jmap histogram but with retained heap (shallow + everything only reachable through this object).

**Shallow vs Retained**:

| Metric | Meaning |
|--------|---------|
| Shallow Heap | Size of the object itself (not including referenced objects) |
| Retained Heap | Size of the object + all objects that would be GC'd if this object were removed |

**Retained heap is the key metric for finding leaks.** A HashMap with 100 bytes shallow heap might retain 500MB if it's the only reference to cached data.

#### 3. Dominator Tree

Shows objects sorted by retained heap. The "dominator" of an object is the closest GC root that must keep the object alive.

**Interpretation**:
- If one object retains > 20% of heap, it's almost certainly a leak
- If the top 3 dominators retain > 50% of heap, investigate all three
- Flat dominator tree (many similar-sized objects) indicates bloat, not a leak

### OQL Queries for Minecraft-Specific Objects

Object Query Language (OQL) in MAT lets you search the heap with SQL-like syntax:

```sql
-- Find all Entity objects
SELECT * FROM net.minecraft.world.entity.Entity

-- Find HashMap instances larger than 1MB retained
SELECT * FROM java.util.HashMap h WHERE h.@retainedHeapSize > 1048576

-- Find all Thread objects
SELECT * FROM java.lang.Thread

-- Find PluginClassLoader instances (hot-reload leak)
SELECT * FROM org.bukkit.plugin.java.PluginClassLoader

-- Find Connection objects (connection leak)
SELECT * FROM net.minecraft.network.Connection

-- Find large String instances (> 10KB retained)
SELECT * FROM java.lang.String s WHERE s.@retainedHeapSize > 10240

-- Find Netty ByteBuf arenas (direct buffer leak)
SELECT * FROM io.netty.buffer.PoolArena

-- Find large ConcurrentHashMap instances
SELECT * FROM java.util.concurrent.ConcurrentHashMap c WHERE c.@retainedHeapSize > 1048576

-- Count entity types
SELECT class, COUNT(*) FROM net.minecraft.world.entity.Entity GROUP BY class

-- Find objects retained by a specific plugin's class loader
SELECT * FROM OBJECTS WHERE OBJECTS.@classLoader = (SELECT c FROM org.bukkit.plugin.java.PluginClassLoader c WHERE c.pluginIdentifier.toString() = 'MyPlugin')

-- Find all Chunk objects (chunk leak check)
SELECT * FROM net.minecraft.world.level.chunk.Chunk

-- Find ThreadLocal maps with many entries
SELECT * FROM java.lang.ThreadLocal$ThreadLocalMap WHERE @retainedHeapSize > 1048576

-- Find SoftReference count (reference cache leak indicator)
SELECT COUNT(*) FROM java.lang.ref.SoftReference

-- Find RegionFile objects (region cache check)
SELECT * FROM net.minecraft.world.level.chunk.storage.RegionFile

-- Find ByteBuffer direct buffers (netty leak indicator)
SELECT * FROM java.nio.DirectByteBuffer
```

### Finding What's Holding References

The key question in leak analysis: "Why can't the GC collect this object?"

**Method 1: Path to GC Root**
1. Right-click an object → "Path to GC Roots" → "exclude weak/soft references"
2. This shows the chain of strong references keeping the object alive
3. Follow the chain to find the GC root (static field, thread, etc.)

**Method 2: Incoming References**
1. Right-click an object → "Incoming References"
2. Shows all objects that reference this one
3. Iterate through incoming references until you find the one(s) keeping it alive

**Method 3: Merge Shortest Paths to GC Root**
1. Select a set of leaked objects
2. Right-click → "Merge Shortest Paths to GC Root" → "exclude weak references"
3. Shows the common root keeping all of them alive
4. This is usually the source of the leak

**Common GC Roots in Minecraft**:

| Root Type | What It Is | Common Leak Pattern |
|-----------|-----------|-------------------|
| Static field | Class-level variable | Private static Map in plugin |
| Thread | Running thread | Plugin thread pool not shut down |
| JNI global | Native reference | Netty direct buffer |
| System class | JDK class | `java.util.logging` handler |
| ThreadLocal | Per-thread variable | Plugin ThreadLocal not removed |

---

## Fixing Common Memory Issues

### Entity Count Reduction

| Method | Config File | Setting | Impact |
|--------|------------|---------|--------|
| Reduce spawn-limits | bukkit.yml | `monster: 30`, `animal: 5`, `water-animal: 3`, `ambient: 2` | 50-70% fewer entities |
| Entity per-chunk limits | paper-world.yml | `entity-per-chunk-save-limit` per type | Hard cap per chunk |
| Increase despawn ranges | paper-world.yml | `despawn-ranges.hard.horizontal: 36` | Faster natural despawn |
| Reduce activation range | spigot.yml | `entity-activation-range` | Less per-entity processing |
| Item merge radius | spigot.yml | `merge-radius.item: 3.5` | Fewer item entities on ground |
| Exp merge radius | spigot.yml | `merge-radius.exp: 4.0` | Fewer exp orb entities |
| Nerf spawner mobs | spigot.yml | `nerf-spawner-mobs: true` | Disable AI for mob spawner entities |

### Chunk Tuning for Memory

| Method | Config File | Setting | Impact |
|--------|------------|---------|--------|
| Reduce view-distance | server.properties | `view-distance: 6-8` | 30-60% fewer loaded chunks |
| Reduce simulation-distance | server.properties | `simulation-distance: 4` | 40-70% fewer ticking chunks |
| No chunk delay | paper-global.yml | `delay-chunk-unloads-by: 0` | Immediate unload |
| Pre-generate worlds | Chunky plugin | Pre-gen 5-10k radius | Eliminate chunk gen lag |
| Set world border | Chunky/WorldBorder | Border at 5-10k | Cap total chunks |
| Limit non-player chunk loads | paper-world.yml | `max-auto-save: 8` | Reduce save overhead |

**Memory impact of view distance**:

| View Distance | Loaded Chunks (per player) | Approx Memory per Player | At 50 Players |
|---------------|--------------------------|--------------------------|---------------|
| 4 | 81 (9×9) | ~15MB | ~750MB |
| 6 | 169 (13×13) | ~30MB | ~1.5GB |
| 8 | 289 (17×17) | ~55MB | ~2.75GB |
| 10 | 441 (21×21) | ~85MB | ~4.25GB |
| 12 | 625 (25×25) | ~120MB | ~6GB |

**Rule**: Each view-distance increment roughly doubles chunk memory. Dropping from 10 to 8 saves ~40% of chunk memory.

### String Deduplication

Add `-XX:+UseStringDeduplication` to JVM flags (G1GC only, JDK 8u20+).

**Expected impact**: 10-25% reduction in String/char[] memory for Minecraft servers with many player names, item names, and chat messages.

**Not compatible with ZGC**. ZGC does not support String deduplication.

**How it works**: During GC, G1 identifies duplicate String objects and makes them share the same underlying `char[]`. The deduplication runs as part of the concurrent mark cycle with negligible overhead.

**When to enable**:

| Condition | Recommendation |
|-----------|----------------|
| Using G1GC, heap > 8GB | Enable |
| Using G1GC, heap < 8GB | Usually not worth it |
| Using ZGC | Not available |
| String/char[] > 25% of heap | Definitely enable |
| String/char[] < 15% of heap | Probably not worth it |

**How to verify it's working**:

```bash
# Add to JVM flags for GC logging:
-Xlog:gc+stringdedup*=debug:file=gc.log

# After running for 30+ minutes, check:
grep "StringDedup" gc.log
# Look for lines like: "StringDedup: ... deduplicated ... strings"
```

### Direct Buffer Management

1. **Add Netty leak detection** during debugging: `-Dio.netty.leakDetection.level=PARANOID`
2. **Limit direct memory** (if suspected as issue): `-XX:MaxDirectMemorySize=256m`
3. **Check plugin network handlers** for ByteBuf not released in all code paths
4. **Monitor direct memory**: `jcmd <pid> VM.native_memory summary | grep Internal`

**Direct memory sizing guide**:

| Player Count | Recommended MaxDirectMemorySize | Notes |
|-------------|-------------------------------|-------|
| < 50 | 128M | Default is fine, don't set limit |
| 50-200 | 256M | Set limit if seeing direct buffer growth |
| 200-500 | 512M | Recommended for mid-size servers |
| > 500 | 1G | For large proxy/network servers |

### Plugin Cache Sizing

Replace unbounded HashMap/ConcurrentHashMap with properly sized caches:

| Cache Type | Recommended | Max Size | TTL |
|-----------|-------------|----------|-----|
| Player data | Caffeine | 2× peak players | 30min after access |
| Block location lookup | Caffeine | 50K entries | 10min after write |
| Name/UUID mapping | Caffeine | 10K entries | 1hour after write |
| Computation result | Caffeine | 5K entries | 5min after write |
| Skin/texture cache | Caffeine | 10K entries | Never (use weakKeys) |

Caffeine Maven dependency:
```xml
<dependency>
    <groupId>com.github.ben-manes.caffeine</groupId>
    <artifactId>caffeine</artifactId>
    <version>3.1.8</version>
</dependency>
```

Caffeine Gradle dependency:
```groovy
implementation 'com.github.ben-manes.caffeine:caffeine:3.1.8'
```

### ThreadLocal Cleanup Patterns

Always clean up ThreadLocal values. Two approaches:

**Pattern 1: Try-Finally (Recommended)**
```java
private static final ThreadLocal<Context> CTX = new ThreadLocal<>();

public void handle() {
    try {
        CTX.set(new Context());
        doWork();
    } finally {
        CTX.remove();
    }
}
```

**Pattern 2: Custom Thread Pool with AfterExecute Cleanup**
```java
ExecutorService pool = new ThreadPoolExecutor(...) {
    @Override
    protected void afterExecute(Runnable r, Throwable t) {
        CTX.remove();
        super.afterExecute(r, t);
    }
};
```

**Pattern 3: Plugin onDisable Cleanup**
```java
@Override
public void onDisable() {
    // Cancel all scheduled tasks
    Bukkit.getScheduler().cancelTasks(this);
    
    // Shut down thread pools
    if (executor != null) {
        executor.shutdownNow();
    }
    
    // Clear caches
    playerCache.invalidateAll();
    
    // Unregister listeners
    HandlerList.unregisterAll(this);
}
```

### Quick Diagnosis Checklist

When memory is high, check in this order:

1. **Run `/spark gc`** — Is GC pressure the problem?
2. **Run `/spark heapsummary`** — What types dominate the heap?
3. **Run `jmap -histo:live <pid> | head -30`** — Get concrete numbers
4. **Run `heapdump_analyzer.py leak-check --jmap-histogram histogram.txt`** — Check known patterns
5. **Is old gen growing?** — `jstat -gcutil <pid> 5000 12` for 1 minute
6. **Is it a leak or bloat?** — Full GC test (see decision tree above)
7. **Which plugin?** — `/spark plugin-heap <name>` or spark_toolkit `plugin-heap`
8. **Deep dive** — Full heap dump + Eclipse MAT if needed

**Time budget**:

| Step | Time | Tool |
|------|------|------|
| Steps 1-3 | 2 minutes | Spark + jmap |
| Step 4 | 1 minute | heapdump_analyzer |
| Step 5 | 2 minutes | jstat monitoring |
| Step 6 | 5 minutes | Full GC test |
| Step 7 | 3 minutes | spark plugin-heap |
| Step 8 | 30-60 minutes | MAT analysis |

Most memory issues can be diagnosed in under 15 minutes using steps 1-7. Reserve step 8 for genuine leaks that require reference chain analysis.