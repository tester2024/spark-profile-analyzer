# Spark Toolkit AI Usage Examples

Complete examples for every `spark_toolkit.py` command, showing input and expected output structure.

## fetch

```bash
python spark_toolkit.py fetch https://spark.lucko.me/abc123 --full
```

```json
{
  "profile_id": "abc123",
  "metadata_available": true,
  "profile_type": "sampler",
  "platform": {"type": "SERVER", "name": "Bukkit", "version": "git-Paper-386", "minecraft_version": "1.19.3"},
  "full_data": { ... },
  "raw_data": {"available": true, "type": "sampler", "content_type": "application/x-spark-sampler", "size_bytes": 123456, "size_human": "120.6 KB"}
}
```

## info

```bash
python spark_toolkit.py info https://spark.lucko.me/abc123
```

```json
{
  "source_type": "json_url",
  "profile_type": "sampler",
  "platform": {"type": "SERVER", "name": "Bukkit", "version": "git-Paper-386", "minecraft_version": "1.19.3"},
  "tps": {"1m": {"value": 19.8, "status": "GOOD"}, "5m": {"value": 19.5, "status": "GOOD"}, "15m": {"value": 19.2, "status": "WARNING"}},
  "mspt": {"1m": {"mean": 28, "median": 25, "p95": 42, "max": 120, "min": 12}, "ideal_mspt": 50},
  "system": {"cpu_model": "AMD Ryzen 9 5950X", "cpu_threads": 32, "java_version": "17.0.6"},
  "heap": {"used": 6144, "committed": 8192, "max": 12288},
  "gc": {"G1 Young Generation": {"total_collections": 450, "avg_time_ms": 15, "avg_frequency": 2.5}},
  "plugins_mods": {"Essentials": {"name": "Essentials", "version": "2.19.7"}},
  "sampler": {"interval_ms": 4, "mode": "EXECUTION", "engine": "ASYNC"}
}
```

## threads

```bash
python spark_toolkit.py threads https://spark.lucko.me/abc123 --thread server --top 5
```

```json
{
  "total_threads": 24,
  "matched_threads": 1,
  "threads": [{
    "name": "Server thread",
    "total_time": 30000,
    "sleep_time": 12000,
    "sleep_pct": 40.0,
    "tick_time": 18000,
    "tick_pct": 60.0,
    "health": "MODERATE",
    "top_children": [
      {"class": "net.minecraft.server.MinecraftServer", "method": "tick", "time": 18000, "pct": 60.0},
      {"class": "net.minecraft.server.MinecraftServer", "method": "waitForNextTick", "time": 12000, "pct": 40.0}
    ]
  }]
}
```

## tree

```bash
python spark_toolkit.py tree https://spark.lucko.me/abc123 --thread server --plugin "com.essentials" --min-pct 2 --max-depth 6 --limit 20
```

```json
{
  "threads": [{
    "thread": "Server thread",
    "total_time": 30000,
    "nodes": [
      {"class": "com.essentials.EventHandler", "method": "onPlayerJoin", "time_total": 1500, "time_pct": 5.0, "depth": 3, "path": "... -> onPlayerJoin"},
      {"class": "com.essentials.tasks.AutoSaveTask", "method": "run", "time_total": 900, "time_pct": 3.0, "depth": 4, "path": "... -> AutoSaveTask.run"}
    ],
    "total_nodes_found": 2
  }]
}
```

## hotspots

```bash
python spark_toolkit.py hotspots https://spark.lucko.me/abc123 --thread server --exclude-sleep --min-pct 2 --limit 10
```

```json
{
  "hotspots": [
    {"class": "net.minecraft.world.level.Level", "method": "tickNonBlocking", "self_time": 6000, "total_time": 12000, "self_pct": 20.0, "total_pct": 40.0, "thread": "Server thread", "path": "MinecraftServer.tick -> Level.tickNonBlocking"},
    {"class": "org.bukkit.craftbukkit.v1_19_R2.scheduler.CraftScheduler", "method": "mainThreadHeartbeat", "self_time": 3000, "total_time": 4500, "self_pct": 10.0, "total_pct": 15.0, "thread": "Server thread", "path": "MinecraftServer.tick -> CraftScheduler.mainThreadHeartbeat"}
  ],
  "total_found": 15
}
```

## plugins

```bash
python spark_toolkit.py plugins https://spark.lucko.me/abc123
```

```json
{
  "sources": [
    {"source": "Minecraft", "time": 18000, "pct": 60.0},
    {"source": "Essentials", "time": 4500, "pct": 15.0},
    {"source": "WorldGuard", "time": 3000, "pct": 10.0},
    {"source": "Unknown", "time": 4500, "pct": 15.0}
  ],
  "grand_total": 30000
}
```

## tps

```bash
python spark_toolkit.py tps https://spark.lucko.me/abc123
```

```json
{
  "tps": {"1m": {"value": 18.5, "status": "WARNING"}, "5m": {"value": 19.2, "status": "WARNING"}, "15m": {"value": 19.8, "status": "GOOD"}, "target": 20},
  "mspt_1m": {"mean": 35, "median": 28, "p95": 48, "max": 150, "min": 12, "median_status": "WARNING", "p95_status": "WARNING", "max_status": "CRITICAL"},
  "mspt_5m": {"mean": 30, "median": 25, "p95": 42, "max": 200, "min": 10, "median_status": "GOOD", "p95_status": "WARNING", "max_status": "CRITICAL"},
  "ideal_mspt": 50,
  "windows": [{"window_id": "0", "ticks": 400, "tps": 19.5, "tps_status": "GOOD", "mspt_median": 25, "mspt_max": 80, "players": 45, "entities": 1200}]
}
```

## gc

```bash
python spark_toolkit.py gc https://spark.lucko.me/abc123
```

```json
{
  "platform": {
    "G1 Young Generation": {"total_collections": 450, "avg_time_ms": 15, "avg_frequency_per_min": 2.5, "avg_time_status": "WARNING", "avg_frequency_status": "WARNING"},
    "G1 Old Generation": {"total_collections": 3, "avg_time_ms": 350, "avg_frequency_per_min": 0.02, "avg_time_status": "CRITICAL", "avg_frequency_status": "GOOD"}
  }
}
```

## search

```bash
python spark_toolkit.py search https://spark.lucko.me/abc123 "tickEntities" --thread server --limit 5
```

```json
{
  "pattern": "tickEntities",
  "regex": false,
  "matches": [
    {"class": "net.minecraft.server.level.ServerLevel", "method": "tickNonBlocking", "time": 12000, "thread": "Server thread", "path": "... -> tickNonBlocking", "depth": 4},
    {"class": "net.minecraft.world.level.entity.EntityTickList", "method": "forEach", "time": 8000, "thread": "Server thread", "path": "... -> EntityTickList.forEach", "depth": 5}
  ],
  "total_found": 2
}
```

## callpath

```bash
python spark_toolkit.py callpath https://spark.lucko.me/abc123 "Essentials.onPlayerJoin" --thread server
```

```json
{
  "target": "Essentials.onPlayerJoin",
  "paths": [{
    "thread": "Server thread",
    "thread_total_time": 30000,
    "path": [
      {"class": "java.lang.Thread", "method": "run", "time": 30000},
      {"class": "net.minecraft.server.MinecraftServer", "method": "run", "time": 28000},
      {"class": "net.minecraft.server.MinecraftServer", "method": "tick", "time": 18000},
      {"class": "org.bukkit.craftbukkit.scheduler.CraftScheduler", "method": "mainThreadHeartbeat", "time": 4500},
      {"class": "com.essentials.EventHandler", "method": "onPlayerJoin", "time": 1500}
    ],
    "depth": 5,
    "self_time": 1500,
    "pct_of_thread": 5.0
  }],
  "total_found": 1
}
```

## heap

```bash
python spark_toolkit.py heap https://spark.lucko.me/abc123 --limit 5
```

```json
{
  "total_types": 850,
  "total_instances": 2500000,
  "total_size_bytes": 5368709120,
  "total_size_human": "5.00 GB",
  "top_entries": [
    {"type": "byte[]", "instances": 500000, "size_bytes": 1073741824, "size_human": "1.00 GB", "size_pct": 20.0},
    {"type": "net.minecraft.world.entity.Entity", "instances": 45000, "size_bytes": 536870912, "size_human": "512.0 MB", "size_pct": 10.0}
  ]
}
```

## entities

```bash
python spark_toolkit.py entities https://spark.lucko.me/abc123 --entity-type "wolf" --min-entities 5
```

```json
{
  "total_entities": 15000,
  "entity_counts": {"wolf": 3000, "zombie": 5000, "sheep": 4000},
  "worlds": [{
    "name": "world",
    "total_entities": 12000,
    "regions": [{
      "total_entities": 12000,
      "chunks": [{"x": 5, "z": 10, "total_entities": 50, "entity_counts": {"wolf": 45}}]
    }]
  }]
}
```

## compare

```bash
python spark_toolkit.py compare https://spark.lucko.me/abc123 --window-a 0 --window-b 3
```

```json
{
  "window_a": "0",
  "window_b": "3",
  "comparison": {
    "tps": {"window_a": 20.0, "window_b": 16.5, "change_pct": -17.5},
    "mspt_median": {"window_a": 25, "window_b": 55, "change_pct": 120.0},
    "mspt_max": {"window_a": 60, "window_b": 350, "change_pct": 483.3},
    "players": {"window_a": 10, "window_b": 80, "change_pct": 700.0}
  }
}
```

## report

```bash
python spark_toolkit.py report https://spark.lucko.me/abc123 -o analysis.json
```

Generates a full analysis with:
- Platform info, TPS/MSPT, GC data
- Thread health assessment
- Top hotspots per thread
- Plugin/source attribution
- Auto-generated findings with CRITICAL/WARNING/LOW severity