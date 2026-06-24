# Spark Toolkit Commands Reference

Full reference for every `spark_toolkit.py` command, its flags, and targeting/filtering options.

## Command Summary

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
| `heap` | Heap summary with plugin attribution | `--type-filter`, `--plugin`, `--limit` |
| `entities` | Entity/world statistics | `--entity-type`, `--min-entities` |
| `plugin-heap` | Heap usage attributed to a specific plugin | `--plugin` (required), `--limit` |
| `plugin-profile` | Complete plugin performance profile (CPU + heap + findings) | `--plugin` (required) |
| `search` | Search stack traces by pattern | `pattern`, `--regex`, `--thread`, `--limit` |
| `callpath` | Trace call path to a method | `method`, `--regex`, `--thread`, `--limit` |
| `compare` | Compare two time windows | `--window-a`, `--window-b` |
| `report` | Full analysis with findings | - |
| `analyze-gc` | Deep GC analysis with tuning recommendations | - |
| `analyze-tps` | TPS/MSPT analysis with lag spike detection | - |
| `analyze-cpu` | CPU usage analysis with process/system breakdown | - |
| `recommend` | Performance recommendations with priority actions | - |
| `check-config` | JVM flags + server config analysis with gamemode-aware safety checks | `--platform`, `--gamemode`, `--config-dir`, `--server-properties`, `--spigot-yml`, `--bukkit-yml`, `--paper-global-yml`, `--paper-world-yml`, `--canvas-config`, `--velocity-config`, `--purpur-config`, `--pufferfish-config` |
| `pipeline` | Analyze netty pipeline handler chain and detect duplicate shaded handlers | `--thread` (default: `netty`), `--detect-duplicates` |

## Command Details

### fetch
Fetches raw profile data from a spark URL. Use when you need the raw protobuf/JSON data.
```bash
python spark_toolkit.py fetch https://spark.lucko.me/abc123
python spark_toolkit.py fetch https://spark.lucko.me/abc123 --full  # include decoded raw data
```

### info
Returns platform/metadata summary: Minecraft version, server software, CPU, Java, heap, GC, plugins, sampler config.
Use this as the **first command** to understand the server context.
```bash
python spark_toolkit.py info https://spark.lucko.me/abc123
```

### threads
Lists threads with time breakdown and automatic health assessment (based on sleep percentage).
```bash
python spark_toolkit.py threads https://spark.lucko.me/abc123 --thread server --top 10
```

### tree
Shows the profiler call tree with filtering. Use to drill down into what a specific thread or plugin is doing.
```bash
python spark_toolkit.py tree https://spark.lucko.me/abc123 --thread server --plugin "com.example" --min-pct 2 --max-depth 6 --limit 20
```

### hotspots
Finds the top CPU/self-time hotspots. The **primary command for finding lag sources**.
```bash
python spark_toolkit.py hotspots https://spark.lucko.me/abc123 --thread server --exclude-sleep --min-pct 2 --limit 10
```

### plugins
Attributes time to plugins/mods by mapping class packages. Use to answer "which plugin is causing lag?".
```bash
python spark_toolkit.py plugins https://spark.lucko.me/abc123
python spark_toolkit.py plugins https://spark.lucko.me/abc123 --plugin "Essentials"
```

### tps
Returns TPS/MSPT data with automatic health status assessment (GOOD/WARNING/CRITICAL).
```bash
python spark_toolkit.py tps https://spark.lucko.me/abc123
```

### gc
Returns GC statistics with health status. Use to detect GC pauses causing lag spikes.
```bash
python spark_toolkit.py gc https://spark.lucko.me/abc123
```

### heap
Returns heap summary with automatic plugin attribution. Shows top object types by size/instances and which plugins own them.
```bash
python spark_toolkit.py heap https://spark.lucko.me/abc123
python spark_toolkit.py heap https://spark.lucko.me/abc123 --plugin "com.example" --limit 10
```

### plugin-heap
Attributes heap memory usage to a specific plugin. Reports matched types, total size, instance count, percentage of total heap, and assessment level (CRITICAL > 10%, WARNING > 5%, LOW otherwise).
```bash
python spark_toolkit.py plugin-heap https://spark.lucko.me/abc123 --plugin "Essentials"
```

### plugin-profile
Complete performance overview for a specific plugin: CPU time breakdown, top hot methods, heap usage, allocation hotspots, GC pressure indicators, and auto-generated findings with severity levels.
```bash
python spark_toolkit.py plugin-profile https://spark.lucko.me/abc123 --plugin "MyPlugin"
```

### entities
Returns entity/world statistics. Use to find dense entity hotspots.
```bash
python spark_toolkit.py entities https://spark.lucko.me/abc123
python spark_toolkit.py entities https://spark.lucko.me/abc123 --entity-type "wolf" --min-entities 5
```

### search
Searches stack traces by pattern. Supports regex. Use to find specific methods or classes in the profile.
```bash
python spark_toolkit.py search https://spark.lucko.me/abc123 "tickEntities" --thread server --limit 5
python spark_toolkit.py search https://spark.lucko.me/abc123 "net\.minecraft\.world" --regex --thread server
```

### callpath
Traces the call path from the thread root to a specific method. Use to understand how a hotspot method is reached.
```bash
python spark_toolkit.py callpath https://spark.lucko.me/abc123 "MyPlugin.onTick" --thread server
```

### compare
Compares two time windows. Use to see how performance changed between different time periods.
```bash
python spark_toolkit.py compare https://spark.lucko.me/abc123 --window-a 0 --window-b 3
```

### report
Generates a full analysis report with auto-generated findings. Includes platform info, TPS/MSPT, GC, thread health, hotspots, plugin attribution, heap summary, and severity-tagged findings.
```bash
python spark_toolkit.py report https://spark.lucko.me/abc123
python spark_toolkit.py report https://spark.lucko.me/abc123 -o analysis.json
```

### pipeline
Analyzes the Netty channel pipeline handler chain. By default targets threads whose name contains `netty`; pass `--thread` with a different substring (or multiple) to broaden. Use `--detect-duplicates` to flag duplicate shaded handlers (a common cause of duplicate compression/encryption and needless CPU).
```bash
python spark_toolkit.py pipeline https://spark.lucko.me/abc123
python spark_toolkit.py pipeline https://spark.lucko.me/abc123 --thread netty --detect-duplicates
python spark_toolkit.py pipeline https://spark.lucko.me/abc123 --thread "Netty Server" --thread "Netty Client"
```

## Targeting & Filtering Flags

### Thread Targeting (`--thread`, `-t`)
Filter analysis to specific threads. Supports shortcuts and substring matching:
```bash
--thread server          # Matches "Server thread", "Server", "main"
--thread netty           # Matches any thread with "netty" in name
--thread region          # Matches Folia region threads
--thread "Worker-"       # Matches threads starting with "Worker-"
--thread server netty    # Multiple threads (space-separated)
```

### Plugin/Source Targeting (`--plugin`, `-p`)
Filter calls to only those originating from a specific plugin/mod package:
```bash
--plugin "com.example.myplugin"   # Only calls within this package
--plugin "me.author"              # All plugins by this author
--plugin "io.papermc"             # Paper-specific code
```

### Class/Method Filtering (`--class-filter`, `-c`)
Regex-based filtering on the full `class.method` signature:
```bash
--class-filter "tickEntities"             # Any method containing "tickEntities"
--class-filter "net\.minecraft\.world"    # All NMS world code
--class-filter "PathNavigation"           # All pathfinding code
--class-filter "ChunkProviderServer"      # Chunk loading code
```

### Percentage Threshold (`--min-pct`)
Only show nodes that represent at least N% of the thread's total time:
```bash
--min-pct 5.0    # Only nodes using >= 5% of thread time
--min-pct 1.0   # Only nodes using >= 1% (default for hotspots)
```

### Depth Control (`--max-depth`)
Limit how deep to traverse the call tree:
```bash
--max-depth 5    # Only show first 5 levels
--max-depth 20   # Deeper analysis
```

### Sleep Exclusion (`--exclude-sleep`)
Remove sleep/park/wait entries from hotspot results to focus on actual work:
```bash
--exclude-sleep   # Hides waitForNextTick, Thread.sleep, LockSupport.park, etc.
```

### Output Limiting (`--limit`)
Cap the number of results returned:
```bash
--limit 10    # Top 10 results only
--limit 100   # More thorough
```

### Output Control
```bash
--output report.json   # Write to file instead of stdout
--indent 0             # Compact JSON (no whitespace)
--indent 4             # Pretty with 4-space indent
```

---

## check-config

Analyzes JVM flags and server configuration files for performance issues, bug-configs, and gamemode-specific safety violations.

### Source Data

Config data comes from two sources:
1. **Embedded in spark profile** - `serverConfigurations` field contains `server.properties`, `spigot.yml`, `bukkit.yml`, Paper configs, Canvas `canvas-server.json5`, and more (parsed automatically)
2. **Local files** - Provide via `--config-dir` or individual file flags (parsed from filesystem)

Supported file formats:
- `server.properties` - Java properties format (key=value)
- `.yml` files - Simple YAML (spigot.yml, bukkit.yml, paper-global.yml, paper-world.yml, pufferfish.yml, purpur.yml)
- `.json` files - Standard JSON
- `.json5` files - JSON5 (with comments, trailing commas, unquoted keys - used by Canvas)
- `.toml` files - Velocity config (velocity.toml)

Both sources are merged, with local files taking precedence.

### Gamemode-Aware Analysis

The `--gamemode` flag controls which safety rules and thresholds are applied. **If not specified, the toolkit auto-detects the gamemode** from spark profile data:

- Scans plugin list for gamemode-specific keywords (bedwars, skyblock, factions, lobby, etc.)
- Checks platform name for modded (Forge/Fabric/NeoForge)
- Falls back to `smp` (survival) if no specific gamemode is detected

The output includes `gamemode` (always present) and `gamemode_source` ("auto_detected" or "user_specified").

| Gamemode | Philosophy |
|---|---|
| `smp` (default fallback) | Preserve vanilla gameplay, farms must work, mob behavior intact |
| `lobby` | Aggressive optimization OK, no gameplay requirements |
| `bedwars` | Combat mechanics must work (max-entity-collisions >= 4, merge-radius stays low) |
| `skyblock` | Farm and hopper functionality critical, simulation-distance >= 4 |
| `factions` | PvP fairness, player visibility, arrow persistence important |
| `creative` | Maximize view-distance, minimize entity processing |
| `modded` | Conservative changes, mods may require default activation ranges |
| `unknown` | Conservative defaults, minimal gamemode-specific assumptions |

### Usage

```bash
# Basic - uses config data embedded in spark profile
python spark_toolkit.py check-config https://spark.lucko.me/abc123 --gamemode smp

# With local config directory (auto-finds all config files)
python spark_toolkit.py check-config https://spark.lucko.me/abc123 --gamemode skyblock --config-dir /path/to/server/

# With individual config files
python spark_toolkit.py check-config https://spark.lucko.me/abc123 --gamemode bedwars \
  --server-properties /path/to/server.properties \
  --spigot-yml /path/to/spigot.yml \
  --bukkit-yml /path/to/bukkit.yml \
  --paper-global-yml /path/to/paper-global.yml \
  --paper-world-yml /path/to/paper-world-defaults.yml

# With Canvas/Velocity/Purpur configs
python spark_toolkit.py check-config https://spark.lucko.me/abc123 --gamemode smp \
  --config-dir /path/to/server/ \
  --canvas-config /path/to/canvas-server.json5 \
  --velocity-config /path/to/velocity.toml \
  --purpur-config /path/to/purpur.yml \
  --pufferfish-config /path/to/pufferfish.yml

# Specify platform for platform-specific checks
python spark_toolkit.py check-config https://spark.lucko.me/abc123 --platform paper --gamemode smp
```

### What It Checks

**JVM Analysis:**
- GC type detection (G1GC, ZGC, Parallel, CMS)
- Heap sizing (Xms = Xmx check)
- Aikar's G1GC flags completeness
- ZGC flag recommendations
- Bad flag detection (Parallel GC, CMS)
- G1HeapRegionSize for large heaps

**Game Config Checks (gamemode-aware):**
- `simulation-distance` >= 4 for gameplay worlds (CRITICAL if below)
- `view-distance` >= `simulation-distance`
- `mob-spawn-range` <= `simulation-distance - 1` and >= 3
- `hopper-transfer` = 8 (CRITICAL if set to 1)
- `max-entity-collisions` >= 3 (CRITICAL if below)
- `merge-radius.item` not too high for gamemode (bedwars, skyblock)
- `nerf-spawner-mobs` warning for SMP/skyblock
- `tick-inactive-villagers: false` warning for SMP/skyblock
- `entity-activation-range` exceeds `(sim-dist - 1) * 16`
- `entity-tracking-range.players` >= 48 for PvP servers
- `arrow-despawn-rate` >= 100 for PvP servers
- `entity-per-chunk-save-limit` not set (security issue)
- `despawn-ranges.hard.horizontal` >= 36
- `prevent-moving-into-unloaded-chunks` recommendation
- `alt-item-despawn-rate` recommendation for SMP/skyblock
- `redstone-implementation` optimization recommendation
- `online-mode` security check

### Output Structure

```json
{
  "platform": { "name": "Bukkit", "version": "...", "minecraft_version": "..." },
  "jvm_analysis": {
    "raw_flags": "...",
    "heap_max": "8G",
    "heap_init": "8G",
    "detected_gc": "G1GC"
  },
  "config_analysis": {
    "files_parsed": ["server_properties", "spigot", "bukkit", "paper_global", "paper_world"],
    "findings_count": 5
  },
  "parsed_configs": {
    "server_properties": { "view-distance": 7, "simulation-distance": 4, ... },
    "spigot": { "world-settings": { ... } },
    "bukkit": { "spawn-limits": { ... } },
    "paper_global": { ... },
    "paper_world": { ... },
    "canvas_config": { "performance": { ... }, ... },
    "velocity_config": { ... },
    "purpur_config": { ... },
    "pufferfish_config": { ... }
  },
  "gamemode": "smp",
  "recommendations": [
    {
      "severity": "CRITICAL",
      "category": "bug_config",
      "setting": "hopper-transfer",
      "current": "1",
      "detail": "hopper-transfer=1 makes hoppers process every tick...",
      "action": "Set hopper-transfer to 8 (default). This is a NEVER-CHANGE value."
    },
    ...
  ]
}
```

### Finding Severity Levels

| Level | Meaning |
|---|---|
| `CRITICAL` | Will cause server lag or break gameplay. Fix immediately. |
| `WARNING` | Significant issue that should be addressed. |
| `LOW` | Minor optimization or improvement. |
| `INFO` | Informational note, not a problem. |

### Advanced JVM Flag Analysis

The `check-config` command now analyzes **30+ JVM flags** beyond just GC type and heap size. Each flag is categorized and assessed:

**Flags analyzed:**

| Category | Flags |
|---|---|
| **GC** | UseG1GC, UseZGC, UseParallelGC, UseConcMarkSweepCMS, ZUncommit, SoftMaxHeapSize, UseStringDeduplication |
| **Memory** | Xms/Xmx equality, AlwaysPreTouch, UseTransparentHugePages, UseCompactObjectHeaders, SoftRefLRUPolicyMSPerMB, AutoBoxCacheMax, AlwaysPreTouchStacks |
| **JIT Compiler** | CICompilerCount, UseCriticalCompilerThreadPriority, UseCriticalJavaThreadPriority, SegmentedCodeCache, ReservedCodeCacheSize, NonProfiledCodeHeapSize, ProfiledCodeHeapSize, DontCompileHugeMethods, MaxInlineLevel, MaxInlineSize, FreqInlineSize, InlineSmallCode, LoopUnrollLimit, UseSuperWord, UseVectorMacroLogic, UseFMA, UseCMoveUnconditionally, AlwaysActAsServerClassMachine |
| **CPU** | ActiveProcessorCount (checked against actual cores), UseAVX (checked for CPU compatibility) |
| **System Properties** | log4j2.formatMsgNoLookups, file.encoding, java.security.egd, user.timezone, add-modules=jdk.incubator.vector |
| **Platform-Specific** | Canvas config, Velocity config, Purpur config, Pufferfish config |

**Assessment categories:** CRITICAL, WARNING, LOW, INFO for each finding, plus specific recommendations and safe values.

See `references/jvm-flags-advanced.md` for complete documentation of every flag.

| Category | What It Covers |
|---|---|
| `bug_config` | Configs that improve performance but introduce bugs |
| `config_dependency` | Configs that must be changed together |
| `gameplay_break` | Configs that break vanilla mechanics | 
| `gamemode_break` | Configs that break specific gamemode functionality |
| `security` | Security-related config issues |
| `optimization` | Performance optimization opportunities |
| `jvm` | JVM flag issues |
| `gc` | GC type issues |
| `gc_tuning` | GC tuning flag issues |
| `zgc` | ZGC-specific notes |