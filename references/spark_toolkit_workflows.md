# Spark Toolkit Workflows & Diagnosis Patterns

Step-by-step analysis workflows and common diagnosis patterns for using `spark_toolkit.py`.

## Analysis Workflows

### General Lag Analysis Workflow

Use when the user reports general server lag without specifying a cause.

1. **`info`** -- Get server context (platform, Java, plugins)
2. **`tps`** -- Get TPS/MSPT health status
3. **`threads --thread server --top 10`** -- See server thread breakdown
4. **`hotspots --thread server --exclude-sleep`** -- Find the bottlenecks
5. **`plugins`** -- Attribute time to specific plugins/mods
6. If focused analysis needed: `tree --plugin <name>` or `search <pattern>`
7. For lag spikes: `callpath <method>` to trace how a hotspot is reached
8. For memory issues: `gc` and `heap`
9. For entity lag: `entities --entity-type <type>`
10. Generate final report: `report`

### Plugin Optimization Workflow

Use when the user wants to optimize a specific plugin/mod.

1. **`info`** -- Get server context and confirm the plugin is installed
2. **`plugins`** -- See how much total time the plugin consumes
3. **`tree --plugin "com.example.myplugin" --thread server --min-pct 1`** -- See exact call tree for the plugin
4. **`hotspots --thread server --class-filter "com.example.myplugin" --exclude-sleep`** -- Find the plugin's hottest methods
5. **`callpath "MyPlugin.hotMethod" --thread server`** -- Trace how expensive methods are reached from the tick loop
6. **`gc`** -- Check if the plugin is causing GC pressure (frequent short GC cycles = high allocation rate)
7. **`heap --plugin "com.example.myplugin"`** -- See what object types from this plugin dominate the heap
8. If allocation profile available: `hotspots --class-filter "com.example.myplugin"` to find allocation sites
9. Summarize findings: report which methods are slowest, whether the issue is CPU or memory, and suggest fixes

### Heap Summary Analysis Workflow

Use when the user provides heap summary data (from `/spark heapsummary`).

1. **`heap`** -- Get top heap consumers by type and size
2. **`heap --plugin "com.example"`** -- Filter to types from a specific plugin package
3. Cross-reference with `gc` -- High heap usage + frequent GC = memory pressure from those types
4. Cross-reference with `plugins` -- If a plugin owns many heap objects AND uses high CPU, it's a double problem
5. **`entities`** -- Entity objects are often top heap consumers; check entity counts
6. Identify: object types with unusually high instance counts (potential leak), types with large per-instance size (bloat), byte[]/char[] from String-heavy plugins (inefficient data structures)

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

### Pattern: Plugin causing high CPU time
```
plugins -> MyPlugin is 35%
tree --plugin "com.example.myplugin" --thread server
hotspots --class-filter "com.example.myplugin" --exclude-sleep
  -> MyPlugin.onTick: 18% self-time
  -> MyPlugin.calculatePaths: 12% self-time
callpath "MyPlugin.calculatePaths" --thread server
```
Fix: Optimize the identified hot methods. Move heavy computation to async. Cache results.

### Pattern: Plugin causing memory pressure
```
heap --plugin "com.example.myplugin"
  -> com.example.myplugin.CacheEntry: 500MB, 2M instances
gc -> G1 Young Gen avg_frequency: 8/min (high = lots of short-lived objects)
```
Fix: Reduce cache size, use weak references, implement eviction, reduce object creation rate.

### Pattern: Plugin allocation storm (from --alloc profiler)
```
plugins -> MyPlugin is 45% of allocation
hotspots --class-filter "com.example.myplugin" --exclude-sleep
  -> MyPlugin.buildPacket: allocating 2GB/min
```
Fix: Object pool, reuse buffers, reduce per-tick allocations.

### Pattern: Entity pathfinding lag (common with mob plugins)
```
hotspots --thread server --exclude-sleep
  -> PathNavigation.tick: 15%
  -> EntityTickList.forEach: 10%
entities --entity-type "custom_mob"
  -> 5000 custom_mob in one world
```
Fix: Reduce mob count, increase pathfinding interval, disable pathfinding for idle mobs.

### Pattern: Scheduling lag from too many runnables
```
hotspots --thread server --class-filter "CraftScheduler"
  -> CraftScheduler.mainThreadHeartbeat: 12%
plugins -> plugin using most scheduler time
tree --plugin "com.example.myplugin" --thread server
```
Fix: Reduce scheduled task frequency, merge tasks, move to async where possible.

### Pattern: Heap dominated by byte[]/String from a plugin
```
heap -> byte[]: 2GB (40%), instances: 500K
heap --plugin "com.example.myplugin"
  -> com.example.myplugin.PacketBuffer: large
```
Fix: Use byte buffer pooling, reduce string concatenation, use primitive types over boxed types.

### Pattern: Detecting memory leaks from heap summary
```
heap -> MyPlugin$Listener: 50K instances, 800MB
  (expected: <100 instances)
gc -> frequent full GC with no heap reduction
```
Fix: Listeners not being unregistered, static collections growing, event handlers holding references.