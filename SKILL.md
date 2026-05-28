---
name: spark-profile-analyzer
description: Analyzes Lucko Spark profiler data for Minecraft servers. Handles spark.lucko.me viewer URLs, .sparkprofile files, raw protobuf sampler/heap/health data, JSON exports, and local files. This skill should be used when the user shares a spark.lucko.me link, provides a .sparkprofile file, asks about Minecraft server lag/TPS/MSPT, requests analysis of a spark profiler output, mentions spark tick/gc/heap issues, wants to find which plugin/mod is causing lag, wants to optimize a specific plugin/mod, provides a heap summary or profiler output, asks "what is causing lag", mentions slow ticks or high MSPT, or asks to diagnose performance issues from profiler data.
---

# Spark Profile Analyzer (Lucko Spark)

Analyze Lucko Spark profiler data for Minecraft servers using `scripts/spark_toolkit.py` for structured JSON output.

## When to Activate

| Trigger | Examples |
|---|---|
| Shares a spark profiler URL | "https://spark.lucko.me/abc123" |
| Provides a spark profile file | ".sparkprofile", "profile.json" |
| Asks about server lag | "my server is lagging", "what is causing lag" |
| Mentions TPS/MSPT issues | "low TPS", "high MSPT", "tick lag" |
| Mentions GC/heap issues | "GC pauses", "high memory", "heap summary" |
| Wants to optimize a plugin/mod | "optimize MyPlugin", "which plugin causes lag" |
| Provides heap summary data | "heap summary shows...", "/spark heapsummary" |
| Mentions entity lag | "too many entities", "entity lag" |
| Mentions allocation issues | "high allocation", "memory leak" |
| Wants config review/recommendations | "review my server config", "optimize my setup", "what should I change" |
| Mentions gamemode-specific optimization | "optimize for Bedwars", "best config for SMP", "lobby server setup" |
| Shares server config files | "here's my server.properties", "review my spigot.yml" |
| Asks about specific config settings | "what should hopper-transfer be", "is merge-radius safe" |
| Mentions config bugs/issues | "items disappearing", "mobs not spawning", "farms broken after config change" |

## Supported Input Formats

| Input Type | Description |
|---|---|
| `spark.lucko.me/<id>` URL | Viewer URL; fetched and parsed automatically |
| Profile ID (e.g. `abc123`) | Short form; equivalent to the full URL |
| `.sparkprofile` file | Local spark profile data (JSON or protobuf) |
| Local JSON file | Any previously saved spark profile JSON |
| Inline JSON | Pasted JSON data |

## Prerequisites

The toolkit requires `protobuf` for parsing `.sparkprofile` binary files. Install before use:

```bash
# Linux/macOS
pip3 install protobuf

# Windows
pip install protobuf

# Or using requirements.txt
pip install -r scripts/requirements.txt
```

If protobuf is not installed, the toolkit will still work with JSON data and spark URLs, but will fail on binary `.sparkprofile` files with a clear error message. Use `python3` on Linux/macOS and `python` on Windows.

## Commands Overview

All analysis goes through `scripts/spark_toolkit.py`. Every command outputs structured JSON.

| Command | What It Does | When to Use |
|---|---|---|
| `info` | Platform/metadata summary | **Always first** -- understand server context |
| `tps` | TPS/MSPT with health status | Quick health check; answer "is server lagging?" |
| `threads` | List threads with health assessment | See which threads are overloaded |
| `hotspots` | Top CPU/self-time hotspots | **Primary lag-finding command**; find bottlenecks |
| `plugins` | Attribute time to plugins/mods | Answer "which plugin causes lag?" |
| `tree` | Profiler call tree with filtering | Drill down into what a thread/plugin is doing |
| `search` | Search stack traces by pattern | Find a specific method/class in the profile |
| `callpath` | Trace call path to a method | Understand how a hotspot is reached |
| `gc` | GC statistics with health status | Detect GC pauses causing lag spikes |
| `heap` | Heap summary with plugin attribution | Find what's using memory |
| `check-config` | Analyze JVM flags + server config files with gamemode-aware safety checks | **Config review**; finds bug-configs, dependency issues, and gameplay-breaking settings |
| `plugin-heap` | Heap attributed to one plugin | Check a specific plugin's memory usage |
| `plugin-profile` | Complete plugin perf profile (CPU+heap+findings) | Deep-dive on one plugin |
| `pipeline` | Analyze netty pipeline handler chain and detect duplicate shaded handlers | Find netty pipeline issues and shaded library conflicts |
| `entities` | Entity/world statistics | Find dense entity hotspots |
| `compare` | Compare two time windows | See performance changes over time |
| `report` | Full analysis with findings | Generate complete report with auto-findings |
| `fetch` | Fetch raw profile data | Need raw protobuf/JSON data |
| `health` | Full health report data | Need complete health data |

### Quick Start

```bash
python3 spark_toolkit.py info https://spark.lucko.me/abc123
python3 spark_toolkit.py tps https://spark.lucko.me/abc123
python3 spark_toolkit.py hotspots https://spark.lucko.me/abc123 --exclude-sleep --thread server
python3 spark_toolkit.py plugins https://spark.lucko.me/abc123
python3 spark_toolkit.py report https://spark.lucko.me/abc123

# Heap/memory analysis
python3 spark_toolkit.py heap https://spark.lucko.me/abc123
python3 spark_toolkit.py plugin-heap https://spark.lucko.me/abc123 --plugin MyPlugin
python3 spark_toolkit.py gc https://spark.lucko.me/abc123

# Netty pipeline analysis (detect duplicate shaded handlers)
python3 spark_toolkit.py pipeline https://spark.lucko.me/abc123 --detect-duplicates

# Folia/Canvas analysis (native idle detection works correctly)
python3 spark_toolkit.py threads https://spark.lucko.me/abc123 --thread Region
python3 spark_toolkit.py hotspots https://spark.lucko.me/abc123 --thread Region --exclude-sleep

# Config review - analyze server configs from profile data (automatically parses server.properties, spigot.yml, bukkit.yml, paper-global.yml, paper-world.yml, canvas-server.json5, etc.)
python spark_toolkit.py check-config https://spark.lucko.me/abc123 --gamemode smp

# Config review - also provide local config files (supports .yml, .json, .json5, .properties, .toml)
python spark_toolkit.py check-config https://spark.lucko.me/abc123 --gamemode skyblock --config-dir /path/to/server/

# Config review - provide individual config files including Canvas, Velocity, Purpur, Pufferfish
python spark_toolkit.py check-config https://spark.lucko.me/abc123 --gamemode bedwars \
  --server-properties server.properties \
  --spigot-yml spigot.yml \
  --bukkit-yml bukkit.yml \
  --canvas-config canvas-server.json5 \
  --velocity-config velocity.toml \
  --purpur-config purpur.yml \
  --pufferfish-config pufferfish.yml
```

## Workflow Summary

### General Lag Analysis
1. `info` -> `tps` -> `threads --thread server --top 10` -> `hotspots --thread server --exclude-sleep` -> `plugins` -> drill down with `tree`/`search`/`callpath` -> `report`

### Plugin Optimization
1. `info` -> `plugins` -> `tree --plugin <name>` -> `hotspots --class-filter <name>` -> `callpath <method>` -> `gc` -> `heap --plugin <name>` -> summarize findings

### Heap/Memory Analysis
1. `heap` -> `plugin-heap --plugin <name>` -> cross-ref with `gc` and `plugins` -> `entities` -> identify leaks/bloat

### Heap Dump Analysis (External)
1. Collect heap dump: `jmap -dump:format=b,file=heap.hprof <pid>` or `/spark heapsummary`
2. Analyze with `scripts/heapdump_analyzer.py analyze --jmap-histogram histogram.txt`
3. Or connect to running server: `scripts/heapdump_analyzer.py analyze --pid <pid>`
4. Check leak patterns: `scripts/heapdump_analyzer.py leak-check --jmap-histogram histogram.txt`
5. Cross-reference with spark data: `heap` -> `plugin-heap` -> `gc` -> correlate findings

### Netty Pipeline Analysis
1. `pipeline --thread netty --detect-duplicates` -> identify handler chain and shaded duplicates
2. Cross-reference with `hotspots --thread netty` -> see which handlers consume the most time

### Server Config Review
1. `info` -> identify platform, version, player count -> `check-config <source> --gamemode <type>` -> review findings with severity labels -> cross-reference with spark data (TPS, entity counts) -> present recommendations with risk labels WARN about bug-configs and dependency issues

### Server Config Review (Gamemode-Aware)
1. `info` -> identify platform, version, plugins (gamemode type) -> ask user for config files or extract from analysis -> identify server type (SMP / Lobby / Bedwars / Skyblock / Factions / Creative / Modded) -> cross-reference spark findings with config -> generate gamemode-specific recommendations with safety checks -> WARN about bug-configs and dependency issues -> present with risk labels

**CRITICAL**: When reviewing configs, you MUST:
- Determine the server gamemode BEFORE recommending any config changes
- Never recommend settings that break core gameplay for that gamemode
- Always warn about bug-configs (settings that improve performance but introduce bugs)
- Check config dependencies (e.g., spawn-limits + mob-spawn-range must be adjusted together)
- Label every recommendation with a risk level ([SAFE] / [LOW RISK] / [MODERATE RISK] / [HIGH RISK] / [BRAKE WARNING] / [NEVER])
- Flag settings that should NEVER be changed (hopper-transfer=8, max-entity-collisions>=3, simulation-distance>=4 for gameplay worlds)

See `references/server-config-review.md` for the complete gamemode-specific configuration guide, bug-config warnings, safety rules, and review checklist.

---

## References

### `references/spark_toolkit_commands.md` -- Commands, Flags & Filtering

**What it is:** Complete syntax reference for every `spark_toolkit.py` command, every flag each command accepts, and all targeting/filtering options.

**Why use it:** The command overview table above only tells you *what* a command does at a high level. When you actually run a command, you need to know the exact flags available, what values they accept, and how they combine. This reference has the full breakdown for every single flag including:
- `--thread` -- how substring matching works, multi-thread selection, shortcut names
- `--plugin` -- package name matching and scoping
- `--class-filter` -- regex patterns for class.method signatures
- `--min-pct` -- percentage thresholds to cut noise
- `--max-depth` -- tree depth limits
- `--exclude-sleep` -- removing idle frames from hotspots
- `--limit` -- capping result counts
- `--output` / `--indent` -- output file and formatting control
- Each command's specific usage examples

**When to look at it:**
- Before running a command to construct the right command line with correct flags
- When you know *what* you want (e.g. "filter to a plugin") but not *how* to express it (e.g. `--plugin "com.example"` vs `--class-filter`)
- When a command returns too much noise and you need to narrow results with targeting flags
- When you forget the exact flag name or syntax (`--min-pct` vs `--min-percentage`)

---

### `references/spark_toolkit_workflows.md` -- Workflows, Checklists & Diagnosis Patterns

**What it is:** Step-by-step analysis workflows, a comprehensive analysis checklist, and a library of common diagnosis patterns with their signature symptoms and recommended fixes.

**Why use it:** Knowing individual commands isn't enough -- you need to know *which commands to run in what order* for each situation. This reference provides:
- **3 complete workflows** -- General Lag Analysis (10 steps), Plugin Optimization (9 steps), Heap Summary Analysis (6 steps) with exact command lines at each step
- **8-item analysis checklist** -- Platform context, TPS assessment, server thread tree, plugin attribution, lag spike detection, memory/GC analysis, entity stats, allocation profiling -- with key call frames table showing what each frame means and when to worry
- **12 diagnosis patterns** -- Each pattern shows the exact command sequence that reveals the problem, the output signature to look for, and the fix. Covers: entity tick time, plugin scheduler lag, chunk I/O blocking, low sleep/overworked, GC pause spikes, plugin high CPU, plugin memory pressure, allocation storms, pathfinding lag, scheduling lag, byte[]/String heap dominance, and memory leak detection

**When to look at it:**
- At the **start of any analysis** to pick the right workflow (general lag vs plugin optimization vs heap analysis)
- When you've found a symptom (e.g. "WorldServer.tickEntities is top hotspot") and need to know the next diagnostic steps
- When you see a specific pattern in output and want to match it against known diagnosis patterns to find the fix
- When the user asks "what should I check?" or "what do I do next?" -- follow the relevant workflow

---

### `references/spark_toolkit_output.md` -- Output Formats & Health Assessments

**What it is:** Threshold tables and status level definitions that the toolkit uses to automatically assess server health. Covers thread health, TPS/MSPT status levels, GC status, and plugin-heap assessment.

**Why use it:** Commands like `tps`, `threads`, `gc`, and `plugin-heap` return status labels (GOOD/WARNING/CRITICAL, HEALTHY/MODERATE/OVERLOADED). This reference explains exactly what thresholds produce each label so you can:
- Understand what a "WARNING" TPS status actually means numerically (15-19.5 TPS)
- Know when MSPT is critical (>45ms median, >60ms P95, >150ms max)
- Interpret thread health (sleep >50% = HEALTHY, <20% = OVERLOADED)
- Judge GC severity (frequency >5/min = CRITICAL, avg pause >200ms = CRITICAL)
- Assess plugin heap impact (>10% heap = CRITICAL, >5% = WARNING)
- Understand what fields the `report` and `plugin-profile` commands include in their output

**When to look at it:**
- When interpreting `tps` output and you see a status label but need to understand the exact threshold
- When `threads` reports OVERLOADED and you need to know what sleep percentage that corresponds to
- When `gc` shows WARNING/CRITICAL and you need the numeric thresholds to explain severity to the user
- When `plugin-heap` returns an assessment and you need to contextualize what the threshold means
- When you need to know what sections/fields the `report` or `plugin-profile` output contains

---

### `references/spark_toolkit_examples.md` -- Command Input/Output Examples

**What it is:** Complete worked examples for every single `spark_toolkit.py` command, showing the exact command line and the full JSON output structure with realistic field values.

**Why use it:** The commands reference tells you the *syntax*, but this shows you the *shape of the output*. When parsing or reasoning about command results, you need to know:
- What top-level keys exist (e.g. `hotspots` returns `{"hotspots": [...], "total_found": N}`)
- What fields each result object has (e.g. each hotspot has `class`, `method`, `self_time`, `total_time`, `self_pct`, `total_pct`, `thread`, `path`)
- What nested structures look like (e.g. `heap` output has `top_entries[]` and `plugin_attribution[]` with different schemas)
- What realistic values look like so you can spot anomalies

**When to look at it:**
- Before running a command to understand what the output will look like
- After getting output when you need to understand what a specific field means or where data lives
- When constructing a multi-step analysis and you need to know which fields from one command to feed into the next (e.g. using `plugin` name from `plugins` output as input to `tree --plugin`)
- When you're surprised by output structure and need to verify it matches expectations

---

### `references/spark_proto_schema.md` -- Protobuf Schema & Data Pipeline

**What it is:** The full protobuf message definitions that underlie Spark's data format -- `SamplerData`, `HeapData`, `HealthData` and all supporting messages (`SamplerMetadata`, `ThreadNode`, `StackTraceNode`, `PlatformStatistics`, `WindowStatistics`, etc.). Also documents the fetch/parse pipeline.

**Why use it:** All spark profile data is originally encoded as protobuf. The toolkit handles decoding internally, but the schema reveals how the data is structured at the source level:
- `SamplerData` contains `threads[]`, `class_sources` (class->plugin mapping), `method_sources`, `time_windows[]`, and `time_window_statistics`
- `ThreadNode` has `name`, `children[]` (StackTraceNode tree), and `times[]` (per-window samples)
- `StackTraceNode` has `class_name`, `method_name`, `line_number`, `times[]`, `children_refs[]`
- `HeapData` has `entries[]` with `type`, `instances`, `size`
- `HealthData` has `time_window_statistics` for TPS/MSPT tracking
- The pipeline: fetch from URL -> check Content-Type -> decode protobuf -> walk tree

**When to look at it:**
- When the toolkit fails to parse data and you need to debug the raw protobuf structure
- When you need to understand how plugin attribution works at the data level (`class_sources` maps class names to plugin names)
- When you need to understand the time window system (how TPS/MSPT trends are stored per window)
- When interpreting raw `fetch --full` output and you need to map fields back to their protobuf message
- When extending or debugging the toolkit script itself

---

### `references/spark_commands.md` -- In-Game /spark Commands

**What it is:** Complete reference for the in-game `/spark` plugin commands that server operators use to collect profiler data. Covers profiling, health monitoring, tick monitoring, GC/memory commands, and platform-specific prefixes.

**Why use it:** The toolkit *analyzes* data that was already collected. This reference tells you how to advise users on *collecting* that data in the first place:
- How to start/stop a profiler (`/spark profiler start --timeout 30`)
- How to target specific threads (`--thread server`, `--thread *`)
- How to profile allocations (`--alloc`, `--alloc-live-only`)
- How to catch lag spikes (`--only-ticks-over 150`)
- How to run health checks (`/spark health --upload`)
- How to generate heap summaries (`/spark heapsummary`)
- How to monitor ticks and GC in real-time (`/spark tickmonitor`, `/spark gcmonitor`)
- Platform prefixes (`/spark` for Bukkit, `/sparkb` for BungeeCord, `/sparkv` for Velocity, `/sparkc` for Forge/Fabric)
- Required permissions (`spark.profiler`, `spark.healthreport`, etc.)
- Recommended collection workflows for general lag, lag spikes, memory issues, and TPS overview

**When to look at it:**
- When the user doesn't have profile data yet and needs guidance on how to collect it
- When the user asks "how do I use spark?" or "what spark command should I run?"
- When you need a specific collection strategy (e.g. lag spikes need `--only-ticks-over`, memory needs `--alloc`)
- When advising on the correct command prefix for the user's platform (Bukkit vs BungeeCord vs Velocity)
- When the user needs to know what permissions to grant

---

### `references/optimization-guide-paperchan.md` -- Paper Chan's Server Optimization Guide

**What it is:** Comprehensive Minecraft server optimization guide extracted from Paper Chan's reference (updated May 2026 for Paper 26.1.2). Covers server configuration, entity control, mob spawning mechanics, JVM flags, common mistakes, and things to avoid.

**Why use it:** After analyzing spark data and identifying *what* is causing lag, this guide tells you *how to fix it* with concrete configuration changes:
- **Pre-generation** with Chunky -- eliminates chunk generation lag permanently
- **View distance & simulation distance** -- chunk count formula, rules for setting values, and their relationship
- **Entity count control** -- target <30% entity tick time, mob density math with spawn-limit/mob-spawn-range cheat sheet tables
- **Mob spawn mechanics** -- visual diagram of spawn ranges, despawn ranges, how simulation-distance/mob-spawn-range/despawn-ranges relate to each other
- **Full config references** for `server.properties`, `bukkit.yml`, `spigot.yml`, `paper-world-defaults.yml`, `paper-global.yml` with recommended values
- **Per-world configuration** -- example configs for the_end, nether, and resource worlds
- **Villager optimization** -- VillagerLobotimizer, tick-rate tuning, FarmControl, alternative loot sources
- **JVM flags** -- Aikar's G1GC flags, Generational ZGC, what NOT to use
- **Common mistakes** -- GHz myth, RAM != performance, TPS vs MSPT, minimum 4 cores
- **Things to avoid** -- MobStacker plugins, lag-removal plugins, silktouch spawners, auto-updating Paper, anti-Fabric plugins
- **Quality of life plugins** -- recommended plugins for permissions, villager control, performance monitoring, utility

**When to look at it:**
- When spark analysis reveals high entity tick time -> check entity count control and spawn-limits recommendations
- When spark shows chunk loading lag -> check pre-generation and view-distance sections
- When you need to recommend specific config values (e.g. "what should spawn-limits be for 50 players?")
- When spark shows villager lag -> check villager optimization section
- When the user asks "how do I fix this?" after a lag diagnosis
- When recommending plugins (villager control, farm control, monitoring)
- When the user has common misconceptions (more RAM = better, GHz comparison)

---

### `references/cpu-analysis.md` -- CPU Usage Analysis

**What it is:** Deep guide on interpreting CPU data from Spark profiler, understanding CPU saturation patterns, thread-level attribution, context switching, and the correlation between CPU and TPS/MSPT.

**Why use it:** CPU data is often misinterpreted. This reference helps you correctly read CPU numbers and distinguish between actual CPU bottlenecks vs other causes of lag:
- **Process vs System CPU** -- how to read multi-core CPU percentages (400% = all 4 cores, not 4x overload)
- **CPU saturation patterns** -- high process CPU (entity/plugin overload), high system CPU + low process (competing processes, I/O), low CPU + high lag (lock contention, I/O wait, network bound)
- **CPU steal on virtualized hosts** -- detection, thresholds (0-2% GOOD, >10% CRITICAL), and the fact that it cannot be fixed by JVM tuning
- **Thread-level CPU attribution** -- normal/warning/critical CPU% for Server Main Thread, Netty, Chunk I/O, GC, Scheduled Pool, Folia region threads
- **Thread imbalance diagnosis** -- main thread bottleneck, slow storage, network load, GC pressure, plugin busy-loop
- **Context switching overhead** -- thresholds, measurement commands, reduction strategies, thread pool sizing impact
- **CPU-TPS correlation** -- expected MSPT at each CPU level, and when CPU does NOT predict TPS (GC, I/O, lock contention)
- **I/O-bound, lock contention, and memory-bound servers** -- diagnosis and fixes for non-CPU bottlenecks
- **Thread pool sizing recommendations** -- Minecraft-specific sizes for each pool type

**When to look at it:**
- When `info` or Spark shows CPU data and you need to interpret what the numbers mean
- When CPU looks high but TPS is fine, or CPU looks low but server is lagging
- When `threads` shows unbalanced thread usage (e.g. main thread 90%, others 10%)
- When analyzing VPS/cloud hosting -- check CPU steal thresholds
- When you suspect the bottleneck is NOT CPU (I/O, lock contention, network)
- When recommending thread pool sizes or diagnosing thread imbalance
- When you need to explain to the user why "CPU is high" doesn't always mean "CPU is the problem"

---

### `references/lag-diagnosis.md` -- Lag Spike & TPS Drop Diagnosis

**What it is:** Systematic approach to identifying and resolving lag using Spark profiler data. Covers MSPT analysis, time window correlation, common lag sources, plugin tracing, Folia region analysis, and lag spike patterns.

**Why use it:** This reference goes deeper than the toolkit workflows by providing detailed diagnostic reasoning for specific lag symptoms:
- **MSPT max vs median divergence** -- how to read the gap (2x = mild, 5-10x = moderate, >10x = severe) and what it means (intermittent spike vs sustained overload)
- **MSPT percentile analysis** -- P50/P90/P95/P99/Max healthy/warning/critical thresholds; if P50 good but P99 bad = spikes, if P50 bad = sustained overload
- **Time window correlation** -- TPS graph patterns (sustained low, periodic dips, burst drops, gradual decline) and their likely causes
- **Entity+TPS and Player+MSPT correlation** -- what rising MSPT with player count means (linear = normal, exponential = reduce view-distance)
- **6 common lag sources with costs and fixes** -- entity ticking (per-entity CPU costs), chunk loading, plugin scheduler, pathfinding, redstone, hoppers
- **3 methods to trace lag to a specific plugin** -- tree view, search/filter, callpath analysis with common entry points
- **Common plugin-induced lag patterns** -- event handler, scheduled task, NMS reflection, entity-scanning, block update, chat broadcast
- **Folia region thread analysis** -- region health indicators and Folia-specific observations
- **Lag spike pattern recognition** -- periodic spikes (scheduler), burst spikes (event-driven), sustained overload -- each with diagnosis steps
- **Entity+TPS and Player+MSPT correlation matrices** with reference numbers for different heap sizes
- **GC lag vs game logic lag distinction** -- quick test table and detailed diagnosis for each

**When to look at it:**
- When `tps` shows MSPT max >> median and you need to understand the spike severity
- When you see TPS drops and need to correlate them with entity counts, player counts, or specific windows
- When you've identified a general category of lag (entities, chunks, plugins) and need detailed costs + fixes
- When tracing lag to a specific plugin -- use the 3 tracing methods
- When analyzing Folia servers with region thread data
- When distinguishing whether lag spikes are from GC or from game logic

---

### `references/gc-analysis-guide.md` -- Deep GC Analysis Patterns

**What it is:** Guide for interpreting garbage collection data from Spark profiler output and making tuning decisions. Covers G1GC, ZGC, allocation rate correlation, memory pressure patterns, and the GC tuning decision tree.

**Why use it:** The toolkit's `gc` command gives you the numbers, but this reference tells you *what they mean and what to do about them*:
- **ZGC analysis** -- cycles vs pauses (the most common misanalysis), when pauses indicate issues, when cycles are concerning, generational ZGC on JDK 21+
- **G1GC analysis** -- young/mixed/full collection types, pause time thresholds (good/warning/critical), frequency interpretation, evacuation failure identification
- **Allocation rate correlation** -- allocation rate -> young gen fill -> young GC frequency -> lag; benchmarks (<100MB/s to >1GB/s) and what drives them
- **3 memory pressure patterns** with timelines: growing old gen -> full GC -> OOM; allocation spike -> GC thrashing; stable high usage -> marginal GC
- **GC impact on TPS** -- how pauses translate to MSPT spikes with calculation, correlation table (avg pause x frequency = TPS loss)
- **Spark avg_frequency x avg_time interpretation matrix** -- high/low combinations and their diagnosis
- **GC tuning decision tree** -- step-by-step: is GC causing lag? -> which algorithm? -> G1 (full GC? young gen pauses? mixed pauses?) -> ZGC (allocation stalls? pause duration? cycle frequency?)
- **Heap size decision** -- current heap vs old gen % recommendations
- **GC algorithm decision** -- when to switch G1GC to ZGC based on heap size, JDK version, player count, pause tolerance
- **12 common GC anti-patterns** with symptoms and fixes
- **Memory leak indicators** -- old gen monotonic growth, full GC frees little, heap dump dominators, metaspace growth, direct buffer leaks

**When to look at it:**
- When `gc` shows WARNING/CRITICAL and you need to understand what GC event types are causing it
- When you see ZGC data and need to correctly distinguish cycles (concurrent, not a problem) from pauses (STW, a problem)
- When G1GC shows full GCs (always a problem) or high-frequency young gen collections
- When you need the GC tuning decision tree to recommend specific JVM flag changes
- When spark shows high allocation rate and you need to identify the source
- When memory pressure patterns match (growing old gen, allocation spikes, marginal GC)
- When you suspect a memory leak vs normal GC behavior

---

### `references/performance-standards.md` -- Performance Threshold Reference

**What it is:** Concrete numeric thresholds for evaluating Minecraft server health across all metrics: TPS, MSPT, GC, CPU, memory, entity counts, chunk counts, player capacity, and thread health.

**Why use it:** This is the definitive "what number is good/bad" reference. While `spark_toolkit_output.md` covers the toolkit's automatic assessments, this reference covers *everything* with more detail and context:
- **TPS** -- 19.5+ GOOD, 15-19.5 WARNING, <15 CRITICAL with context on what each level means for gameplay
- **MSPT** -- median/P95/max thresholds plus breakdown targets per component (entity<10ms, chunks<5ms, plugins<3ms, network<5ms, GC<10ms)
- **GC frequency** -- G1GC young/old and ZGC cycles/pauses separately, with clarification that young gen every 1-2s is NORMAL
- **GC pause duration** -- G1GC (<50ms/50-200ms/>200ms) vs ZGC (<1ms/1-5ms/>5ms), STW only
- **CPU usage** -- process vs system, per-core for Folia, CPU steal for VPS with clear thresholds
- **Memory** -- heap utilization thresholds, OOM warning signs, typical memory breakdown by component
- **Entity counts** -- total per world thresholds plus per-type warning thresholds (items, XP, villagers, minecarts, arrows)
- **Chunk counts** -- loaded chunk thresholds with estimation formula and per-player-per-view-distance table
- **Player count capacities** -- expected max players by RAM and server type (Paper survival, Folia, minigames, modded)
- **Thread health** -- sleep% thresholds with per-thread-type healthy/warning/overloaded ranges
- **Spark-specific** -- avg_frequency and avg_time interpretation, total time contribution thresholds
- **Quick diagnosis table** -- symptom -> likely cause -> what to check

**When to look at it:**
- When you need to judge whether any metric (TPS, MSPT, CPU, RAM, entities, chunks) is healthy or problematic
- When you need component-level MSPT targets (e.g. "is 8ms entity tick time good?")
- When you need per-entity-type warning thresholds (e.g. "are 60 villagers too many?")
- When you need to estimate if a server can handle a certain player count with its RAM
- When you need the quick diagnosis table for a symptom (e.g. "TPS drops with joins" -> max-joins-per-tick)
- When CPU steal is detected and you need the thresholds to judge severity

---

### `references/jvm-gc-tuning.md` -- JVM GC Tuning Reference

**What it is:** Complete JVM flag reference for Minecraft servers covering Aikar's G1GC flags, ZGC flags, common flags, memory sizing, bad flags to avoid, pause time targets, and JDK version recommendations.

**Why use it:** When the diagnosis leads to "tune JVM/GC", this reference provides the exact flags and reasoning:

- **Aikar's G1GC flags** -- complete flag set with detailed explanation of every flag's purpose and why the value was chosen
- **ZGC flags** -- recommended set with ZGC-specific flags (SoftMaxHeapSize, ZAllocationSpikeTolerance, ZGenerational)
- **ZGC cycles vs pauses distinction** -- critical for interpreting Spark data correctly
- **G1GC vs ZGC decision table** -- by heap size, JDK version, player count, pause tolerance, CPU cores, workload
- **Common JVM flags reference** -- quick lookup for any flag with recommended value and impact
- **Memory sizing** -- per-player RAM estimates by server type, base RAM formula, total calculation
- **Bad flags to avoid** -- 12 specific flags with explanations of why they're harmful
- **GC pause time targets** -- direct mapping from pause duration to TPS impact and player experience
- **JDK version recommendations** -- JDK 8 through 23+ with status and notes
- **G1HeapRegionSize recommendations** -- by heap size range

**When to look at it:**
- When spark analysis reveals GC issues and you need to recommend specific JVM flag changes
- When the user asks "what JVM flags should I use?" or "how much RAM should I allocate?"
- When you need to decide between G1GC and ZGC for a specific server
- When you see bad JVM flags in server startup scripts that need correction
- When you need to calculate appropriate heap size based on player count and server type
- When recommending JDK version upgrades for better GC (especially JDK 21+ for generational ZGC)
- When the user shares their startup script and you need to audit it

---

### `references/jvm-flags-advanced.md` -- Advanced JVM Flags Reference

**What it is:** Comprehensive reference for ALL JVM flags used with Minecraft servers beyond GC tuning. Covers CPU flags, JIT compiler flags, memory management flags, system properties, Canvas/Folia-specific flags, and bad flags to avoid.

**Why use it:** The `jvm-gc-tuning.md` reference covers GC flags, but Minecraft servers use many more JVM flags for optimization. This reference covers every flag you'll encounter in production startup scripts:

- **GC Flags** -- G1GC, ZGC, and common GC tuning (see also: `jvm-gc-tuning.md`)
- **Memory & Heap Flags** -- Xms/Xmx, AlwaysPreTouch, TransparentHugePages, CompactObjectHeaders, SoftRefLRUPolicyMSPerMB, AutoBoxCacheMax
- **JIT Compiler Flags** -- CICompilerCount, MaxInlineLevel, MaxInlineSize, FreqInlineSize, InlineSmallCode, LoopUnrollLimit, UseSuperWord, UseVectorMacroLogic, SegmentedCodeCache, ReservedCodeCacheSize, NonProfiledCodeHeapSize, ProfiledCodeHeapSize, DontCompileHugeMethods, UseCriticalCompilerThreadPriority, UseCriticalJavaThreadPriority, UseFMA, UseCMoveUnconditionally, AlwaysActAsServerClassMachine
- **CPU & Thread Flags** -- ActiveProcessorCount (MUST match actual cores), UseAVX (AVX=3 WARNING: requires AVX-512 CPU support)
- **System Properties** -- log4j2.formatMsgNoLookups (Log4Shell mitigation), file.encoding, java.security.egd, user.timezone, net.kyori.ansi.colorLevel, terminal.jline, terminal.ansi, add-modules=jdk.incubator.vector (required for Canvas/Folia)
- **Canvas/Folia-specific** -- required modules, recommended thread pools, region thread sizing
- **Bad Flags to Avoid** -- ParallelGC, CMS, AggressiveOpts, mismatched Xms/Xmx, and more
- **JVM Flag Assessment Template** -- ready-to-use checklist for auditing startup scripts

**When to look at it:**
- When `check-config` reports JVM flag findings and you need to understand what each flag does
- When auditing a startup script for correctness and safety
- When the user has unusual flags like `ActiveProcessorCount`, `UseAVX=3`, `MaxInlineLevel=20`, etc.
- When you see Canvas/Folia startup scripts with `--add-modules=jdk.incubator.vector`
- When evaluating whether a specific JVM flag is safe, recommended, or dangerous
- When comparing the user's current flags against recommended values

---

### `references/server-configs-paper.md` -- Paper/Folia/Canvas Configuration Reference

**What it is:** Complete configuration reference for Paper, Folia, and Canvas servers covering `server.properties`, `paper-global.yml`, `paper-world.yml`, `spigot.yml`, `bukkit.yml` with recommended values by server size.

**Why use it:** After diagnosing lag, you often need to recommend specific configuration changes. This reference gives you exactly what to change for Paper-based servers:
- **server.properties** -- view-distance, simulation-distance, network-compression-threshold with size-specific recommendations
- **paper-global.yml** -- entity-activation-range, entity-tracking-range, packet-limiter, max-joins-per-tick, chunk-loading settings
- **paper-world.yml** -- spawn-limits, chunk-settings, entity-per-chunk-save-limit (per entity type), mob-spawn-rate, tracking-range-y
- **spigot.yml overrides** -- activation-range, tracking-range, merge-radius, hopper-transfer, tick-rates, sensor tick-rates
- **bukkit.yml** -- spawn-limits, ticks-per, chunk-gc
- **Folia-specific** -- region threading config, parallel scheduling concepts, performance notes
- **Canvas-specific** -- async chunks, async mobs, DNS optimization
- **Recommended configs by scale** -- small (<20 players, 8GB), medium (20-60, 16GB), large (60+, 24-32GB) with complete config blocks

**When to look at it:**
- When spark shows high entity tick time on a Paper server -> recommend activation-range and spawn-limits changes
- When spark shows chunk loading lag -> recommend view-distance, simulation-distance, chunk-loading settings
- When spark shows mob spawning overhead -> recommend spawn-limits and mob-spawn-rate changes
- When you need to recommend entity-per-chunk-save-limit values for specific entity types
- When the user is on Folia and you need region threading configuration
- When you need a complete recommended config block for a specific server size
- When adjusting hopper settings (keep transfer at 8!), merge-radius, or arrow despawn rates

---

### `references/server-configs-spigot.md` -- Spigot/Bukkit Configuration Reference

**What it is:** Complete configuration reference for Spigot and Bukkit servers covering `server.properties`, `spigot.yml`, and `bukkit.yml` with recommended values by server size.

**Why use it:** Same purpose as the Paper config reference, but for servers running Spigot (without Paper). Key differences from Paper:
- **No simulation-distance** -- Spigot's `view-distance` controls both ticking and rendering
- **No Paper overrides** -- spigot.yml is the primary config, not overridden by paper-global.yml
- **entity-activation-range** -- Spigot's values are the actual values (not overridden). Includes per-server-size recommendations and detailed explanation that this is *the single most impactful Spigot performance setting*
- **merge-radius** -- item and XP merge recommendations with emphasis on farms
- **hopper-transfer** -- explicit warning to NEVER set to 1, keep at 8
- **mob-spawn-range** -- must be <= view-distance
- **growth modifiers** -- low impact but vine-growth-modifier can reduce jungle lag
- **arrow-despawn-rate** -- especially important for PvP servers
- **nerf-spawner-mobs** and **zombie-aggressive-toward-villager** -- situation-specific recommendation
- **spawn-limits** -- note that on Spigot (without Paper's per-player-mob-spawns), these are multiplicative per player: 70 monsters x 10 players = 700 monsters
- **ticks-per** -- spawn attempt intervals
- **Quick sizing guide** -- small/medium/large server config blocks
- **Common misconfigurations table** -- 8 common mistakes with fixes

**When to look at it:**
- When the server is running Spigot (not Paper) and you need config recommendations
- When the user doesn't have Paper's `simulation-distance` concept (only `view-distance`)
- When you need Spigot-specific entity-activation-range values
- When explaining that Spigot spawn-limits are multiplicative (70 x players) unlike Paper's per-player system
- When you need the quick sizing guide for small/medium/large Spigot servers
- When auditing a Spigot server for common misconfigurations

---

### `references/server-configs-proxy.md` -- BungeeCord/Velocity Proxy Configuration Reference

**What it is:** Complete configuration reference for BungeeCord and Velocity proxies, including JVM flags, memory sizing, load balancer config, and common misconfigurations.

**Why use it:** When the user's architecture includes a proxy, proxy misconfiguration can cause issues that show up in Spark (high network lag, connection timeouts, player join lag):
- **velocity.toml** -- core settings (player-info-forwarding, forwarding-secret-file), [advanced] section (compression-threshold, compression-level, timeouts), [query] section
- **BungeeCord config.yml** -- core settings (connection_throttle, timeout, network_compression_threshold), server definitions, listeners, player limits, tab list
- **Proxy JVM flags** -- different from game servers (I/O-bound, not CPU-bound); 1GB is usually sufficient
- **Proxy memory sizing** -- small (<200 players: 512MB-1GB), medium, large, very large
- **Velocity vs BungeeCord comparison** -- performance, security, plugins, development status
- **Load balancer configuration** -- HAProxy example, proxy-protocol usage, TCP keepalive
- **Common proxy misconfigurations** -- no forwarding secret, online-mode on backends, too much RAM, no connection throttle, backend ports not firewalled

**When to look at it:**
- When spark data comes from a proxy server (BungeeCord/Velocity) or the user mentions proxy issues
- When spark shows connection-related lag (player joins, network processing) on backend servers behind a proxy
- When recommending proxy configuration (compression, forwarding mode, connection throttling)
- When choosing between Velocity and BungeeCord for a new setup
- When the user has a load balancer in front of the proxy and needs configuration guidance
- When auditing for common proxy misconfigurations (missing forwarding secret, backends with online-mode=true)

---

### `references/server-config-review.md` -- Gamemode-Aware Config Review & Bug-Config Warnings

**What it is:** Comprehensive guide for reviewing Minecraft server configurations with gamemode-specific profiles, bug-config warnings, safety rules, and a systematic review checklist. Covers SMP, Lobby, Bedwars, Skywars, Factions, Skyblock, Creative, and Modded server types.

**Why use it:** After spark analysis identifies *what* is causing lag, you need to recommend config changes, but those changes depend entirely on the server's gamemode. A setting that's perfectly fine for a lobby is game-breaking for SMP. This reference prevents you from making recommendations that damage gameplay:

- **Gamemode-specific configuration profiles** -- SMP (preserve vanilla), Lobby (aggressive optimization OK), Bedwars/Skywars (combat mechanics matter), Skyblock (farms and hoppers are critical), Factions/PvP (visibility and combat fairness), Creative (maximize view distance, minimize entities), Modded (research mod requirements first)
- **Bug-config warnings** -- 10 specific configs that improve performance numbers but introduce bugs: hopper-transfer=1 (server-destroying), max-entity-collisions<3 (game-breaking), simulation-distance<4 (farms broken), excessive merge-radius (items teleport), tick-inactive-villagers:false (iron farms broken), and more
- **Absolute never-change rules** -- hopper-transfer must be 8, max-entity-collisions >= 3, simulation-distance >= 4 for gameplay worlds, mob-spawn-range <= sim-dist-1 AND >= 3
- **Conditional never-change rules** -- gamemode-dependent settings that should NOT be changed (don't disable doMobSpawning on SMP, don't lower entity-tracking-range.players on PvP, etc.)
- **Config dependency matrix** -- which configs MUST be changed together (spawn-limits + mob-spawn-range, simulation-distance + despawn-ranges, activation-range + tracking-range)
- **Risk labels** -- [SAFE], [LOW RISK], [MODERATE RISK], [HIGH RISK], [BRAKE WARNING], [NEVER], [DEPENDS]
- **Systematic review checklist** -- 12-point checklist template covering view/sim distance, entity ranges, spawn limits, merge radius, despawn ranges, hopper settings, entity limits, gamerules, JVM flags, per-world configs, bug-config check, and dependency validation
- **Quick-reference gamemode decision matrix** -- every major config value for every gamemode type at a glance

**When to look at it:**
- When the user asks for config review or optimization recommendations
- When spark analysis reveals entity lag and you need to recommend spawn-limit/activation-range changes
- When the user mentions their server gamemode (SMP, Bedwars, etc.) and needs tailored configs
- When recommending any config change -- ALWAYS check the bug-config warnings first
- When the user shares their config files for review
- When the user reports bugs after config changes (items disappearing, mobs not spawning, farms broken)
- When you see a dangerous config like `hopper-transfer: 1` or `max-entity-collisions: 2` in a user's config

---

### `references/cpu-analysis.md`
See detailed entry above. (Duplicate reference path -- content is identical.)

---

### `references/folia-canvas-analysis.md` -- Folia/Canvas Thread Analysis

**What it is:** Deep guide for analyzing Folia and Canvas Minecraft server profiler data, addressing the fact that standard thread health assessment (based on sleep_pct) is broken for region-threaded servers because native parking frames (pthread_cond_wait, parkNanos) are not counted as idle.

**Why use it:** Folia and Canvas servers use region-based parallel ticking. Standard Spark analysis shows all region threads as OVERLOADED with 0% sleep because `LockSupport.parkNanos` and `pthread_cond_timedwait` are not recognized as idle. This reference covers the fix and how to properly analyze Folia/Canvas:

- **Threading model overview** -- Folia (Paper fork with region threading) vs Canvas (Folia fork with AffinitySchedulerThreadPool), how region threads work, why standard thread health fails
- **Thread type table** -- all thread types on Folia/Canvas with name patterns, idle methods, and purposes
- **Idle vs active recognition** -- complete table of idle frame signatures (waitUntilDeadline, parkNanos, pthread_cond_wait, epoll_pwait2) and active frame signatures (tickRegion, forEachTickingEntity, tickBlockEntities)
- **effective_idle_pct** -- the new metric that combines Java sleep and native idle time for accurate Folia/Canvas thread health assessment
- **New health thresholds** -- HEALTHY >= 50%, MODERATE 20-50%, OVERLOADED < 20% (based on effective_idle_pct, not sleep_pct)
- **spark_toolkit.py commands for Folia** -- specific command examples with `--thread Region`, `--exclude-sleep`, `effective_idle_pct` interpretation
- **Region thread performance analysis** -- how to find entity tick dominance, region imbalance, cross-region synchronization
- **Canvas-specific config** -- `canvas-server.json5` options, `--add-modules=jdk.incubator.vector` requirement, thread count recommendations
- **Folia/Canvas config recommendations** -- region-thread-count formula, view-distance vs simulation-distance on Folia, entity activation ranges, parallel scheduling
- **Common Folia/Canvas issues table** -- 10 issues with detection commands, root causes, and fixes
- **Complete command reference** -- 14 commands specifically for Folia/Canvas analysis with interpretation patterns

**When to look at it:**
- When `threads` shows all region threads as OVERLOADED with 0% sleep -- this is the Folia/Canvas idle detection issue
- When analyzing a Folia or Canvas server and needing region-specific analysis commands
- When needing to interpret `effective_idle_pct` vs `sleep_pct` for thread health
- When recommending region-thread-count or other Folia/Canvas-specific configuration
- When diagnosing region imbalance (some regions overloaded, others idle)
- When checking for Canvas-specific requirements (jdk.incubator.vector, async chunks)

---

### `references/heapdump-analysis-guide.md` -- Heap Dump Analysis Guide

**What it is:** Comprehensive guide for analyzing Java heap dumps (.hprof files) for Minecraft servers. Covers collecting heap dumps, using `heapdump_analyzer.py`, interpreting jmap output, identifying memory leaks, and correlating with Spark data. Supports both Windows and Linux.

**Why use it:** When spark `heap` or `gc` data indicates memory pressure, you need deeper analysis. Heap dumps provide the detailed object-level breakdown that spark can't:

- **Collecting heap dumps** -- 9 methods with platform-specific commands: `/spark heapsummary`, `jmap -dump`, `jcmd GC.heap_dump`, Eclipse MAT, VisualVM, and OOM auto-dump
- **Using heapdump_analyzer.py** -- `analyze` (connect to running server or parse jmap output), `commands` (show platform-specific diagnostic commands), `leak-check` (check against known Minecraft leak patterns)
- **Heap histogram analysis** -- jmap -histo:live output interpretation, normal vs abnormal thresholds for every type (entities, chunks, strings, byte[], collections, netty)
- **Minecraft-specific memory patterns** -- what normal heap composition looks like at different scales, when each type becomes a problem
- **Memory leak vs bloat decision tree** -- 4-outcome test (leak vs bloat, old gen growth, full GC effectiveness)
- **8 common leak patterns** -- static collection leak, thread-local leak, listener leak, cache without eviction, reference queue leak, classloader leak, direct buffer leak, region file cache leak
- **GC log indicators** -- old gen monotonic growth, full GC frees little, metaspace growth, allocation rate increase with jstat/jcmd commands
- **Diagnostic commands reference** -- complete tables for both Linux and Windows
- **Correlating with Spark** -- how to cross-reference `spark_toolkit.py heap`, `plugin-heap`, `gc` with heapdump data
- **Eclipse MAT quick reference** -- OQL queries for Minecraft-specific objects, key reports
- **Fixing common memory issues** -- entity reduction, chunk tuning, string deduplication, buffer management, cache sizing, ThreadLocal cleanup

**When to look at it:**
- When spark shows heap usage >70% or GC WARNING/CRITICAL
- When `plugin-heap` shows a plugin using >5% of heap
- When you suspect a memory leak (growing old gen, OOM errors, increasing GC frequency)
- When a user mentions "out of memory", "server crashes", "increasing RAM usage"
- When you need jstat/jmap/jcmd commands for a running server (Windows or Linux)
- When heap dump data is available and you need to identify the root cause of memory pressure

---

### `references/memory-leak-detection.md` -- Memory Leak Detection Reference

**What it is:** Step-by-step guide for detecting, diagnosing, and fixing memory leaks in Minecraft servers using both Spark profiler data and heap dumps. Covers leak indicators visible in spark data, heap dump analysis patterns, and complete diagnostic workflows.

**Why use it:** Memory leaks are one of the hardest issues to diagnose. This reference bridges the gap between spark's runtime data and heap dump analysis:

- **Leak vs bloat definition** -- clear distinction with diagnostic decision tree
- **Detecting leaks from Spark data** -- using `heap`, `plugin-heap`, `gc`, and `plugin-profile` to identify leak patterns
- **Spark GC indicators of leaks** -- 4 key indicators with thresholds: old gen growth, full GC ineffectiveness, allocation rate increase, metaspace growth
- **Detecting leaks from heap dumps** -- `heapdump_analyzer.py analyze` and `leak-check` commands with examples
- **10 Minecraft-specific memory leak patterns** -- entity accumulation, chunk loading leak, connection leak, NBT bloat, plugin cache leak, ThreadLocal leak, listener leak, direct buffer leak, classloader leak, RegionFile cache growth
- **Each pattern includes** -- heap signature, detection command, root cause, severity, and specific fix
- **Complete leak detection workflow** -- step-by-step: spark heap → spark gc → spark plugin-heap → heapdump_analyzer → Eclipse MAT → identify root cause
- **jstat and jcmd reference** -- complete table of useful commands for leak detection

**When to look at it:**
- When spark shows continuously growing heap usage
- When `gc` shows WARNING/CRITICAL with increasing old gen
- When `plugin-heap` shows a plugin whose memory share is growing
- When a user reports "server gets slower over time" or "I have to restart daily"
- When OOM errors appear in server logs
- When `heapdump_analyzer.py leak-check` findings need interpretation

---

## Scripts

- `scripts/spark_toolkit.py` -- Main analysis CLI. All commands and reference docs above describe this script. **Requirements:** `protobuf>=4.21.0` for binary `.sparkprofile` parsing (see `scripts/requirements.txt`). Use `python3` on Linux/macOS, `python` on Windows.
- `scripts/heapdump_analyzer.py` -- Heap dump analyzer for Minecraft servers. Detects memory leaks, bloat, and usage patterns from jmap histograms and running Java processes. Supports both Windows and Linux. No external dependencies (uses jmap/jstat/jcmd which come with JDK). Runs independently from spark_toolkit.py.
- `scripts/requirements.txt` -- Python dependencies: `protobuf>=4.21.0` (required for parsing binary .sparkprofile files)