# Spark Commands Quick Reference

## Profiler Commands

### Basic Profiling
| Command | Description |
|---|---|
| `/spark profiler start` | Start profiler (default mode) |
| `/spark profiler stop` | Stop and upload results |
| `/spark profiler cancel` | Cancel without uploading |
| `/spark profiler open` | Open viewer without stopping |
| `/spark profiler info` | Check profiler status |

### Profiler Flags (start)
| Flag | Description |
|---|---|
| `--timeout <seconds>` | Auto-stop after duration |
| `--thread *` | Profile all threads |
| `--thread <name>` | Profile specific thread |
| `--thread <pattern> --regex` | Profile threads matching regex |
| `--alloc` | Memory allocation profiling mode |
| `--interval <ms>` | Sampling interval (default 4ms) |
| `--only-ticks-over <ms>` | Only profile ticks exceeding threshold |
| `--combine-all` | Merge all threads under one root |
| `--not-combined` | Don't group thread pool threads |
| `--ignore-sleeping` | Only sample active threads |
| `--force-java-sampler` | Use Java sampler instead of async-profiler |

### Profiler Flags (stop)
| Flag | Description |
|---|---|
| `--comment <text>` | Add comment to the viewer |
| `--save-to-file` | Save to config directory instead of uploading |

### Allocation Profiler Flags
| Flag | Description |
|---|---|
| `--alloc-live-only` | Only track objects not garbage collected |
| `--alloc --interval <bytes>` | Allocation sampling rate (default 524287 = 512KB) |

## Health & Monitoring

| Command | Description |
|---|---|
| `/spark health` | Generate health report |
| `/spark health --upload` | Upload and get shareable link |
| `/spark health --memory` | Include detailed memory info |
| `/spark health --network` | Include network usage info |
| `/spark tps` | Show TPS and MSPT |
| `/spark ping` | Show player ping averages |
| `/spark ping --player <name>` | Show specific player ping |

## Tick Monitoring

| Command | Description |
|---|---|
| `/spark tickmonitor` | Toggle tick monitoring on/off |
| `/spark tickmonitor --threshold <percent>` | Report ticks exceeding % over average |
| `/spark tickmonitor --threshold-tick <ms>` | Report ticks exceeding ms duration |
| `/spark tickmonitor --without-gc` | Exclude GC reports |

## Memory & GC

| Command | Description |
|---|---|
| `/spark gc` | Show GC history |
| `/spark gcmonitor` | Toggle GC monitoring on/off |
| `/spark heapsummary` | Generate heap summary |
| `/spark heapsummary --run-gc-before` | Run GC before (deprecated) |
| `/spark heapdump` | Generate .hprof heap dump |
| `/spark heapdump --compress <type>` | Compress (gzip/xz/lzma) |
| `/spark heapdump --include-non-live` | Include GC-eligible objects (deprecated) |
| `/spark heapdump --run-gc-before` | Run GC before (deprecated) |

## Misc

| Command | Description |
|---|---|
| `/spark activity` | Show recent spark activity |
| `/spark activity --page <n>` | View specific page |

## Platform-Specific Command Prefixes

| Platform | Command Prefix |
|---|---|
| Bukkit/Spigot/Paper | `/spark` |
| BungeeCord | `/sparkb` |
| Velocity | `/sparkv` |
| Forge/Fabric Client | `/sparkc` |

## Permissions

All commands require `spark` permission, or the specific sub-permission:
- `spark.profiler`
- `spark.healthreport`
- `spark.ping`
- `spark.tps`
- `spark.tickmonitor`
- `spark.gc`
- `spark.gcmonitor`
- `spark.heapsummary`
- `spark.heapdump`

## Recommended Profiling Workflow

### For General Lag Analysis
1. `/spark profiler start --timeout 30` (30-second profile)
2. Review Server thread in viewer
3. Follow the highest percentages down the tree

### For Lag Spikes
1. `/spark tickmonitor --threshold-tick 50` (detect spikes)
2. Note the spike duration from tickmonitor output
3. `/spark profiler start --only-ticks-over 150` (adjust threshold accordingly)
4. Reproduce the lag spike
5. `/spark profiler stop`
6. Review filtered profile (only slow ticks shown)

### For Memory Issues
1. `/spark gc` (check GC stats)
2. `/spark gcmonitor` (watch GC in real-time)
3. `/spark profiler start --alloc --timeout 30` (allocation profiling)
4. `/spark heapsummary` (heap breakdown by type)

### For TPS/MSPT Overview
1. `/spark tps` (quick check)
2. `/spark health --upload` (full health report with shareable link)