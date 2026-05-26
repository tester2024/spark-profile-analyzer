---
name: spark-profile-analyzer
description: Analyzes Lucko Spark profiler data for Minecraft servers. Handles spark.lucko.me viewer URLs, .sparkprofile files, raw protobuf sampler/heap/health data, JSON exports, and local files. This skill should be used when the user shares a spark.lucko.me link, provides a .sparkprofile file, asks about Minecraft server lag/TPS/MSPT, requests analysis of a spark profiler output, mentions spark tick/gc/heap issues, or wants to find which plugin/mod is causing lag.
---

# Spark Profile Analyzer (Lucko Spark)

Analyze Lucko Spark profiler data for Minecraft servers to identify lag sources, tick bottlenecks, GC pressure, and memory issues. All analysis uses `scripts/spark_toolkit.py` for structured, machine-readable JSON output.

## Supported Input Formats

| Input Type | Description |
|---|---|
| `spark.lucko.me/<id>` URL | Viewer URL; fetched and parsed automatically |
| Profile ID (e.g. `abc123`) | Short form; equivalent to the full URL |
| `.sparkprofile` file | Local spark profile data (JSON or protobuf) |
| Local JSON file | Any previously saved spark profile JSON |
| Inline JSON | Pasted JSON data |

## Script: spark_toolkit.py

**Location**: `scripts/spark_toolkit.py`

Every analysis operation goes through this script. It outputs structured JSON, making it ideal for AI agents to parse and reason about.

### Quick Start

```bash
# Fetch metadata from a spark URL
python spark_toolkit.py info https://spark.lucko.me/abc123

# List threads with health assessment
python spark_toolkit.py threads https://spark.lucko.me/abc123 --thread server

# Find what's causing lag (top hotspots)
python spark_toolkit.py hotspots https://spark.lucko.me/abc123 --exclude-sleep --thread server

# Attribute time to plugins/mods
python spark_toolkit.py plugins https://spark.lucko.me/abc123

# Search for a specific method
python spark_toolkit.py search https://spark.lucko.me/abc123 "WorldServer.tickEntities" --thread server

# Trace the call path to a method
python spark_toolkit.py callpath https://spark.lucko.me/abc123 "MyPlugin.onTick"

# Filter profiler tree to a specific plugin
python spark_toolkit.py tree https://spark.lucko.me/abc123 --plugin "com.example.myplugin"

# Get TPS/MSPT with status assessment
python spark_toolkit.py tps https://spark.lucko.me/abc123

# Check GC health
python spark_toolkit.py gc https://spark.lucko.me/abc123

# Parse a local file
python spark_toolkit.py report ./profile.json

# Generate full analysis report
python spark_toolkit.py report https://spark.lucko.me/abc123 -o report.json
```

### Commands Reference

| Command | Purpose | Key Flags |
|---|---|---|
| `fetch` | Fetch profile data from URL | `--full` |
| `info` | Platform/metadata summary | - |
| `threads` | List threads with health assessment | `--thread`, `--top`, `--top-threads` |
| `tree` | Profiler call tree with filtering | `--thread`, `--plugin`, `--class-filter`, `--min-pct`, `--max-depth`, `--limit`, `--sort-by-pct` |
| `hotspots` | Top CPU/self-time hotspots | `--thread`, `--class-filter`, `--min-pct`, `--exclude-sleep`, `--limit` |
| `plugins` | Attribute time to plugins/mods | `--thread`, `--plugin` |
| `tps` | TPS/MSPT data with status | - |
| `gc` | GC statistics with health status | - |
| `health` | Full health report data | - |
| `heap` | Heap summary with filtering | `--type-filter`, `--plugin`, `--limit` |
| `entities` | Entity/world statistics | `--entity-type`, `--min-entities` |
| `search` | Search stack traces by pattern | `pattern`, `--regex`, `--thread`, `--limit` |
| `callpath` | Trace call path to a method | `method`, `--regex`, `--thread`, `--limit` |
| `compare` | Compare two time windows | `--window-a`, `--window-b` |
| `report` | Full analysis with findings | - |

### Targeting & Filtering Flags

These flags allow precision targeting of specific data, reducing noise and focusing analysis:

#### Thread Targeting (`--thread`, `-t`)

Filter analysis to specific threads. Supports shortcuts and substring matching:

```bash
--thread server          # Matches "Server thread", "Server", "main"
--thread netty           # Matches any thread with "netty" in name
--thread region          # Matches Folia region threads
--thread "Worker-"       # Matches threads starting with "Worker-"
--thread server netty    # Multiple threads (space-separated)
```

#### Plugin/Source Targeting (`--plugin`, `-p`)

Filter calls to only those originating from a specific plugin/mod package:

```bash
--plugin "com.example.myplugin"   # Only calls within this package
--plugin "me.author"              # All plugins by this author
--plugin "io.papermc"            # Paper-specific code
```

#### Class/Method Filtering (`--class-filter`, `-c`)

Regex-based filtering on the full `class.method` signature:

```bash
--class-filter "tickEntities"             # Any method containing "tickEntities"
--class-filter "net\.minecraft\.world"    # All NMS world code
--class-filter "PathNavigation"           # All pathfinding code
--class-filter "ChunkProviderServer"      # Chunk loading code
```

#### Percentage Threshold (`--min-pct`)

Only show nodes that represent at least N% of the thread's total time:

```bash
--min-pct 5.0    # Only nodes using >= 5% of thread time
--min-pct 1.0   # Only nodes using >= 1% (default for hotspots)
```

#### Depth Control (`--max-depth`)

Limit how deep to traverse the call tree:

```bash
--max-depth 5    # Only show first 5 levels
--max-depth 20   # Deeper analysis
```

#### Sleep Exclusion (`--exclude-sleep`)

Remove sleep/park/wait entries from hotspot results to focus on actual work:

```bash
--exclude-sleep   # Hides waitForNextTick, Thread.sleep, LockSupport.park, etc.
```

#### Output Limiting (`--limit`)

Cap the number of results returned:

```bash
--limit 10    # Top 10 results only
--limit 100   # More thorough
```

#### Output Control

```bash
--output report.json   # Write to file instead of stdout
--indent 0             # Compact JSON (no whitespace)
--indent 4             # Pretty with 4-space indent
```

### AI Agent Workflow

1. **Start with `info`** to understand server context (platform, Java, plugins)
2. **Run `tps`** to get TPS/MSPT health status
3. **Run `threads`** with `--thread server --top 10` to see server thread breakdown
4. **Run `hotspots`** with `--thread server --exclude-sleep` to find the bottlenecks
5. **Run `plugins`** to attribute time to specific plugins/mods
6. **If focused analysis needed**: use `tree --plugin <name>` or `search <pattern>`
7. **For lag spikes**: use `callpath <method>` to trace how a hotspot is reached
8. **For memory issues**: use `gc` and `heap`
9. **For entity lag**: use `entities --entity-type <type>`
10. **Generate final report** with `report`

### Thread Health Assessment

The `threads` command automatically assesses thread health based on sleep percentage:

| Sleep % | Health | Meaning |
|---|---|---|
| >50% | HEALTHY | Server has spare capacity |
| 20-50% | MODERATE | Working hard but coping |
| <20% | OVERLOADED | No spare capacity, likely lagging |

### TPS/MSPT Status Levels

TPS and MSPT values are automatically assessed:

| Metric | GOOD | WARNING | CRITICAL |
|---|---|---|---|
| TPS | >= 19.5 | 15 - 19.5 | < 15 |
| MSPT median | < 30ms | 30 - 45ms | > 45ms |
| MSPT P95 | < 45ms | 45 - 60ms | > 60ms |
| MSPT max | < 50ms | 50 - 150ms | > 150ms |
| GC frequency | < 1/min | 1 - 5/min | > 5/min |
| GC avg pause | < 50ms | 50 - 200ms | > 200ms |

## Analysis Checklist

### 1. Platform & Server Context

Use `info` to extract:
- Minecraft version, server software (Paper/Spigot/Fabric/etc.)
- CPU model, thread count, OS, Java version
- JVM arguments (heap size, GC algorithm)
- Player count, uptime
- Installed plugins/mods and versions

### 2. TPS & MSPT Assessment

Use `tps` to get structured TPS/MSPT with automatic health assessment.

### 3. Server Thread Profiler Tree

Use `threads --thread server --top 10` then drill down with `tree --thread server --min-pct 5`.

Key call frames on the Server thread:

| Call Frame | What It Means | Concern If High |
|---|---|---|
| `waitForNextTick()` / `Thread.sleep()` / `LockSupport.park()` | Server sleeping (healthy!) | Low % = server overloaded |
| `MinecraftServer.tick()` | Main game tick work | High % = server working hard |
| `WorldServer.doTick()` / `ServerLevel.tick()` | World ticking | Look deeper for causes |
| `WorldServer.tickEntities()` / `ServerLevel.tickNonBlocking()` | Entity ticking | Common lag source |
| `CraftScheduler.mainThreadHeartbeat()` | Bukkit plugin scheduler | Plugin lag |
| `Pathfinder` / `PathNavigation` | Mob pathfinding | Heavy entity counts |
| `RegionFile` / `RegionFileStorage` | Chunk I/O | Slow disk |

### 4. Plugin Attribution

Use `plugins` to see which plugins/mods are using the most time. Cross-reference with `tree --plugin <name>` for details.

### 5. Lag Spike Detection

Use `hotspots --thread server --exclude-sleep --min-pct 3` to find spike causes. If MSPT max >> median, use `callpath` to trace how hotspots are reached.

### 6. Memory & GC Analysis

Use `gc` to get GC health status. Use `heap` for object type breakdown.

### 7. Entity & World Statistics

Use `entities` to find dense entity hotspots. Use `--entity-type` and `--min-entities` to target specific problems.

### 8. Allocation Profiler Analysis

For `--alloc` mode profiles, use `hotspots` to find allocation-heavy sites.

## Common Diagnosis Patterns

### Pattern: High entity tick time
```
hotspots --thread server --exclude-sleep
  -> WorldServer.tickEntities() is top hotspot
  -> search "ServerEntity" --thread server
  -> entities --entity-type "wolf"
```
Fix: Reduce entity count, use entity-limit plugins.

### Pattern: Plugin scheduler lag
```
plugins -> MyPlugin is 35%
tree --plugin "com.example.myplugin"
```
Fix: Optimize plugin, move work to async.

### Pattern: Chunk I/O blocking
```
search "RegionFile" --thread server
callpath "RegionFile.read" --thread server
```
Fix: Use faster storage, reduce view distance.

### Pattern: Low sleep = overworked
```
threads --thread server
  -> sleep_pct: 5%, health: OVERLOADED
```
Fix: Reduce load or upgrade hardware.

### Pattern: GC pauses causing lag spikes
```
gc -> G1 Old Gen avg_frequency: 12/min, avg_time: 180ms
```
Fix: Increase heap, switch to G1GC/ZGC.

## Report Output Format

Use `report` command for a full analysis. Output includes:
- Platform info
- TPS/MSPT data
- GC statistics
- Thread health assessment
- Top hotspots per thread
- Plugin/source time attribution
- Auto-generated findings with severity levels (CRITICAL/WARNING/LOW)

## Resources

### scripts/
- `spark_toolkit.py` -- Main analysis CLI (14 commands, full filtering/targeting). See command reference above.

### references/
- `spark_proto_schema.md` -- Protobuf message schemas for SamplerData, HeapData, HealthData
- `spark_commands.md` -- Quick reference for all /spark in-game commands and flags