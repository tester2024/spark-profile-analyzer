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
| `plugin-profile` | Complete plugin performance profile (CPU + heap + findings) | `--plugin` (required), `--thread` |
| `search` | Search stack traces by pattern | `pattern`, `--regex`, `--thread`, `--limit` |
| `callpath` | Trace call path to a method | `method`, `--regex`, `--thread`, `--limit` |
| `compare` | Compare two time windows | `--window-a`, `--window-b` |
| `report` | Full analysis with findings | - |

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