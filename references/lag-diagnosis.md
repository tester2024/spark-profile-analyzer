# Lag Spike and TPS Drop Diagnosis

Systematic approach to identifying and resolving lag in Minecraft servers using Spark profiler data.

---

## Detecting Lag Spikes from MSPT Data

### MSPT Max vs Median Divergence

The most reliable indicator of lag spikes is the gap between median MSPT and max MSPT.

| Divergence | Meaning | Severity |
|-----------|---------|----------|
| max < 2× median | Normal variation | None |
| max = 2-5× median | Occasional spikes | Mild |
| max = 5-10× median | Significant spikes | Moderate |
| max > 10× median | Extreme spikes | Severe |

**Example**: median MSPT = 25ms, max MSPT = 250ms
- The server runs smoothly most of the time (25ms < 50ms budget)
- But at least one tick took 250ms (5 missed ticks, ~3 TPS for that moment)
- This divergence pattern indicates an intermittent spike, not sustained overload

### MSPT Percentile Analysis

| Percentile | Healthy | Warning | Critical |
|-----------|---------|---------|----------|
| P50 (median) | < 30ms | 30-45ms | > 45ms |
| P90 | < 40ms | 40-60ms | > 60ms |
| P95 | < 50ms | 50-80ms | > 80ms |
| P99 | < 80ms | 80-150ms | > 150ms |
| Max | < 100ms | 100-200ms | > 200ms |

**Key insight**: If P50 is good but P99 is bad, you have intermittent spikes. If P50 is bad, you have sustained overload. These require different fixes.

---

## Correlating Time Windows with Lag

### TPS Drops in Specific Windows

Check Spark's TPS graph for pattern recognition:

| Pattern | Shape in TPS Graph | Likely Cause |
|---------|-------------------|---------------|
| Sustained low TPS | Flat line below 20 | Overload: too many entities/players for config |
| Periodic dips | Regular valleys at fixed interval | Scheduler task (auto-save, backup, custom plugin) |
| Burst drops | Sharp spikes downward | Chunk load burst, explosion, entity spawn event |
| Gradual decline | Slow downward trend over minutes | Memory pressure building, GC degrading |
| Sudden drop + partial recovery | Sharp drop then settling | Mass player join, world change, teleport |
| Correlated with time-of-day | Drops at specific hours | Player count patterns, scheduled tasks |

### Entity Count + TPS Correlation

```
If TPS drops when entity count rises:
  1. Check if spawn-limits are too high
  2. Check if entity-activation-range is too large
  3. Look for mob farms or spawners creating abnormal entity counts
  4. Check if entity per-chunk-save-limit is set

If TPS drops independently of entity count:
  1. The lag is likely from chunk loading, not entity ticking
  2. Check chunk generation rate
  3. Check for hopper-heavy builds
  4. Investigate plugin scheduler tasks
```

### Player Count + MSPT Correlation

| Observation | Meaning | Action |
|-------------|---------|--------|
| MSPT rises linearly with players | Server load scales expectedly | Normal. Ensure config scales too. |
| MSPT rises exponentially with players | Entity/chunk load is superlinear | Reduce view-distance, spawn-limits |
| MSPT spikes at specific player counts | Threshold effect (e.g., chunk generation kicks in) | Pre-generate worlds |
| MSPT high even with few players | Lag not player-caused | Check plugins, hoppers, redstone |

---

## Common Lag Sources

### 1. Entity Ticking (Most Common)

| Entity | CPU Cost per Tick | Warning Signs | Fix |
|--------|------------------|---------------|-----|
| Villager | Very High (0.5-2ms each) | > 50 villagers active | Lower activation range, nerf AI |
| Zombie/Skeleton | High (0.1-0.5ms each) | > 200 monsters active | Lower spawn limits, wider activation range |
| Item (dropped) | Medium (0.01-0.05ms) | > 500 items in world | Increase merge radius |
| Hopper Minecart | Very High (full tick) | > 10 per chunk | Replace with hopper blocks |
| Ender Dragon | Extreme (5-20ms) | Dragon fight active | Expected; optimize during fight |
| Wither | High (1-5ms) | Wither fight | Expected; contain fight area |

### 2. Chunk Loading

| Operation | Cost | When It Happens | Fix |
|-----------|------|----------------|-----|
| Chunk load (from disk) | 5-20ms | Player moves to unloaded area | Pre-generate, increase view-distance slightly to preload |
| Chunk generate | 50-200ms | First time visiting area | Pre-generate with Chunky/Border |
| Chunk send (to client) | 2-10ms | Player view changes | Reduce view-distance |
| Chunk GC | 1-5ms | Periodically | Normal, not tunable |

**Critical fix**: Pre-generate worlds with Chunky plugin. This eliminates chunk generation lag permanently.

### 3. Plugin Scheduler

| Pattern | How to Identify | Fix |
|---------|----------------|-----|
| Periodic 1-5s lag spikes | Regular interval in MSPT, matches task schedule | Reduce task frequency, make async |
| On-join lag spike | MSPT spikes when players connect | Defer join processing, use max-joins-per-tick |
| Every-30s spike | Auto-save or backup | Increase auto-save interval, async saves |
| Lag from specific plugin | Spark tree view shows plugin package in hot path | Report to plugin dev, find alternative |

### 4. Pathfinding

| Trigger | Cost | How to Spot | Fix |
|---------|------|------------|-----|
| Zombie targeting player | Medium | Spark shows PathfinderGoal in stack | Increase activation range distance, reduce monster count |
| Villager pathfinding | High | Spark shows Village, PathfinderGoal | Lower villager activation range |
| Mob farm excess | High | Many entities + pathfinding in Spark | Nerf spawner mobs, add entity caps |

### 5. Redstone

| Build Type | Cost | How to Spot | Fix |
|-----------|------|------------|-----|
| Clock circuit | Low per tick, sustained | Consistent MSPT at specific chunks | Limit clock speed, use observer-based designs |
| Large piston array | Medium-High | MSPT spikes when pistons fire | Reduce simultanous pistons |
| Comparator chain | Medium | Spark shows BlockData, Redstone | Use alternative logic |
| TNT cannon | Very High (burst) | Extreme MSPT spike, many entity spawns | Limit TNT per activation |

### 6. Hoppers

| Hopper Setup | Cost | How to Spot | Fix |
|-------------|------|------------|-----|
| Single hopper | Low | Normal | No action |
| Hopper pipe (5+) | Medium | Consistent MSPT overhead | Use water streams, minecart+hopper alternatives |
| Sorting system | High | MSPT overhead in specific chunks | Optimize design, avoid 1-item hoppers |
| Hopper minecart | Very High | Per-tick processing | Replace with stationary hoppers where possible |

---

## Tracing Lag to a Specific Plugin Using Spark

### Method 1: Tree View

1. Open Spark's tree view (calltree)
2. Look for packages that are NOT `net.minecraft`, `org.bukkit`, `java`
3. Custom plugin packages appear as `com.yourplugin`, `me.author`, etc.
4. Sort by total time to find the most expensive plugin calls
5. Look for methods taking > 5% of tick time

### Method 2: Search/Filter

1. Search for known plugin package prefixes
2. Filter by thread (main thread for tick lag, async threads for other issues)
3. Look for `Plugin.runTask`, `ScheduledTask`, `BukkitRunnable` entries

### Method 3: Callpath Analysis

1. In Spark viewer, find the hot method at the top of the flame graph
2. Follow the callpath downward
3. When the callpath enters a plugin's package, that plugin is responsible
4. Common entry points:
   - `org.bukkit.craftbukkit.scheduler.CraftScheduler` → plugin scheduled tasks
   - `org.bukkit.craftbukkit.event.CraftEventManager` → plugin event handlers
   - `net.minecraft.server.MinecraftServer.tickServer` → main tick loop

### Common Plugin-Induced Lag Patterns

| Stack Trace Pattern | Plugin Type | Typical Fix |
|--------------------|------------|-------------|
| `EventListener.handleEvent` → plugin package | Event handler | Optimize handler, reduce event priority, async processing |
| `BukkitRunnable.run` → plugin package | Scheduled task | Reduce frequency, make async |
| `NMSHandler` → reflection calls | NMS-dependent plugin | Report to dev, find Paper API alternative |
| `World.getEntities` → loop over entities | Entity-scanning plugin | Report to dev, use chunk entity lists instead |
| `BlockState.update` → many calls | Block-modifying plugin | Batch updates |
| `Player.sendMessage` in loop | Chat/broadcast plugin | Use async, batch packets |

---

## Folia Region Thread Analysis

### Understanding Region Threads

On Folia, the world is split into independent regions that tick in parallel. Each region has its own thread.

### Region Health Indicators

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Region tick time (median) | < 40ms | 40-50ms | > 50ms |
| Region backlog | 0 | 1-3 ticks | > 3 ticks |
| Region entity count | < 500 | 500-1000 | > 1000 |
| Region thread sleep % | > 40% | 20-40% | < 20% |

### Folia-Specific Analysis

| Observation | Meaning | Fix |
|-------------|---------|-----|
| One region lagging, others fine | Localized load (mob farm, redstone) | Spread players, cap entities in that region |
| All regions moderately lagging | System-wide issue (CPU, memory) | More cores or reduce total load |
| Region migration lag | Players crossing region boundaries | Expected transient; optimize by keeping regions stable |
| Global region lagging | Nether portal processing, global schedulers | Reduce global scheduled tasks |

---

## Lag Spike Patterns

### Pattern 1: Periodic Spikes (Scheduler-Driven)

```
MSPT Graph: _/\_/\_/\_/\_/\_/   (regular spikes)
Period: Fixed interval (e.g., every 600 ticks = 30s)
Cause: Scheduled task, auto-save, backup, world save
Fix: Make task async, reduce frequency, spread workload
```

**Diagnosis steps**:
1. Measure the period between spikes
2. Check if period matches any known interval (save interval, backup, plugin config)
3. Cross-reference with Spark's scheduler view

### Pattern 2: Burst Spikes (Event-Driven)

```
MSPT Graph: __/\_________/\____   (sudden sharp spikes)
Cause: Chunk generation, entity spawn burst, explosion, teleport
Fix: Pre-generate, rate-limit entity spawning, smooth teleports
```

**Diagnosis steps**:
1. Check if spike correlates with player activity (join, teleport, death)
2. Check chunk generation metrics during spike window
3. Look for entity count spikes in Spark

### Pattern 3: Sustained Overload (Capacity Exceeded)

```
MSPT Graph: ────────────────        (consistently above 50ms)
Cause: Server cannot handle current load with current config
Fix: Reduce view-distance, entity counts, or increase hardware
```

**Diagnosis steps**:
1. Verify MSPT P50 > 50ms (not just spikes)
2. Check if reducing player count improves MSPT
3. Identify the fixed overhead (entity ticking, plugin baseline)

---

## Window Statistics Correlation

### Entities + TPS Correlation Matrix

| Entity Count | Expected TPS (Paper, 8GB) | Expected TPS (Paper, 16GB) | Expected TPS (Paper, 32GB) |
|-------------|--------------------------|----------------------------|---------------------------|
| < 500 | 20 | 20 | 20 |
| 500-1000 | 19-20 | 20 | 20 |
| 1000-2000 | 17-19 | 19-20 | 20 |
| 2000-3000 | 15-18 | 18-19 | 19-20 |
| 3000-5000 | 12-15 | 15-18 | 18-19 |
| > 5000 | < 10 | 12-15 | 15-18 |

### Players + MSPT Correlation Matrix

| Players | MSPT (view-dist 4) | MSPT (view-dist 6) | MSPT (view-dist 8) |
|---------|-------------------|--------------------|--------------------|
| 10 | 10-20ms | 15-25ms | 20-35ms |
| 25 | 15-25ms | 20-35ms | 30-50ms |
| 50 | 20-35ms | 30-50ms | 45-80ms |
| 100 | 30-50ms | 45-80ms | 80-150ms+ |
| 200 | 50-80ms | 80-150ms+ | Not viable |

---

## Distinguishing GC Lag vs Game Logic Lag

### Quick Test

| Observation | GC Lag | Game Logic Lag |
|-------------|--------|---------------|
| MSPT spikes correlate with GC events in Spark | YES | NO |
| CPU spikes during lag | Usually NO (GC is brief) | YES |
| ALL threads stall simultaneously | YES (STW pause) | NO (only main thread) |
| Network I/O affected | NO (connections alive but paused) | MAYBE |
| Lag is exactly as long as GC pause | YES | NO |

### Detailed Diagnosis

**If you suspect GC lag**:
1. Check Spark's GC section for STW pause frequency and duration
2. Correlate MSPT spikes with GC timestamps
3. Look for patterns: increasing old gen → growing pauses
4. Use `-Xlog:gc*` JVM flag for detailed GC logs

**If you suspect game logic lag**:
1. Check Spark's tick thread view for high CPU method calls
2. Look for specific methods/packages in the flame graph
3. Check entity counts during lag windows
4. Disable suspect plugins one at a time

### The Overlap Case

Both GC and game logic can cause lag simultaneously. The total MSPT is:

```
Effective MSPT = Game_Logic_Time + GC_STW_Pauses_During_Tick
```

A tick that takes 30ms of game logic + 80ms of GC pause = 110ms MSPT even though neither component alone would be "bad" enough to cause lag.

**Action**: Address whichever component is the largest contributor first.