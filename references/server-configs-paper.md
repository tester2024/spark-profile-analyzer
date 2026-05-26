# Paper/Folia/Canvas Configuration Reference

## server.properties

| Config | What it does | Small (<20) | Medium (20-60) | Large (60+) | Performance Impact |
|--------|-------------|-------------|----------------|-------------|-------------------|
| `view-distance` | Chunks sent to clients | 7 | 5-7 | 4-5 | **High** - each increment roughly doubles chunk send + memory per player. Controls rendering only, NOT ticking. |
| `simulation-distance` | Chunks where entities tick | 4 | 4 | 4 | **Very High** - entities in these chunks are processed every tick. Keep as low as possible. |
| `network-compression-threshold` | Packet compression threshold (bytes) | 256 | 256 | 512 | **Medium** - 256 is balanced. -1 disables compression (LAN only). Higher = less CPU, more bandwidth. |
| `online-mode` | Mojang auth | true | true | true | **Low** - auth checks. Set false only for BungeeCord/Velocity (use proxy auth instead). |
| `max-players` | Player limit (display) | 20 | 60 | 100+ | **None** - cosmetic only, does not limit actual connections. |
| `enable-command-block` | Command blocks | false | false | false | **Low** - command block execution per tick. Disable if unused. |
| `entity-broadcast-range-percentage` | % of view-distance for entity updates | 100 | 75 | 50 | **Medium** - lower % means less entity update packets. Trade-off: entities pop in closer. |

---

## paper-global.yml

### entity-activation-range

| Config | What it does | Small | Medium | Large | Impact |
|--------|-------------|-------|--------|-------|--------|
| `animals` | Distance to activate animals | 32 | 16-24 | 8-16 | **High** - fewer active entities = less CPU. Below 16 animals appear frozen until closer. |
| `monsters` | Distance to activate monsters | 32 | 24 | 16 | **High** - monsters need some range for gameplay. 16 minimum for gameplay. |
| `raiders` | Distance to activate raiders | 48 | 32 | 24 | **Medium** - raid mobs. Can be lower if raids aren't common. |
| `misc` | Distance to activate misc entities | 16 | 8 | 4-8 | **High** - items, xp orbs, boats, etc. Lower = less item entity ticking. |
| `water` | Distance for aquatic mobs | 16 | 8-16 | 4-8 | **High** - squid, fish. Usually safe to lower. |
| `villagers` | Distance for villagers | 32 | 16-24 | 8-16 | **High** - villagers are CPU-heavy (pathfinding, breeding). Lower aggressively. |
| `flying-monsters` | Distance for flying monsters | 48 | 32 | 16 | **Medium** - phantoms, etc. |

### entity-tracking-range

| Config | What it does | Small | Medium | Large | Impact |
|--------|-------------|-------|--------|-------|--------|
| `players` | Player tracking distance | 128 | 96 | 64 | **Low** - only affects packet sending, not ticking. |
| `animals` | Animal rendering distance | 48 | 32-48 | 24-32 | **Low** - only visual. Lower = less bandwidth, pop-in. |
| `monsters` | Monster render distance | 64 | 48 | 32 | **Low** - visual only. |
| `misc` | Misc render distance | 32 | 16-24 | 16 | **Low** - item rendering. |
| `other` | Other entities render distance | 64 | 48 | 32 | **Low** - visual. |

### alt-desync-fix

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `fix-entity-pos-desync` | Corrects entity position desync | true | true | Prevents ghost entities but adds small overhead. |

### packet-limiter

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `enabled` | Enable packet rate limiting | true | true | **Medium** - protects against packet flood exploits. |
| `packet-limit` | Per-packet-type rate limit | varies | Keep defaults | Prevents abuse. Overly low limits may kick legitimate players. |
| `kick-message` | Message on kick | - | Customize | Informational only. |

### max-joins-per-tick

| Config | What it does | Default | Recommended |
|--------|-------------|---------|-------------|
| `max-joins-per-tick` | Max new player connections per tick | 5 | 3-5 for large servers |

### chunk-loading

| Config | What it does | Default | Large Servers |
|--------|-------------|---------|--------------|
| `max-queue-size` | Max chunk load queue | 100 | 50-100 (lower = less lag on mass join) |
| `auto-safe-interval` | Auto-save interval (ticks) | -1 (5min) | 12000-24000 (5-10min) |
| `delay-chunk-unloads-by` | Delay before unloading chunks (ticks) | 300 (15s) | 100-200 (5-10s) |

---

## paper-world.yml

### spawn-limits

| Config | What it does | Small | Medium | Large | Impact |
|--------|-------------|-------|--------|-------|--------|
| `monster` | Max monsters per player | 70 | 30-50 | 15-25 | **Very High** - directly controls mob count. Lower = less entity CPU. |
| `animal` | Max animals per player | 10 | 5-8 | 2-5 | **High** - animals are heavy. |
| `water-creature` | Max water creatures per player | 5 | 3 | 2 | **Medium** |
| `water-ambient` | Max water ambient per player | 20 | 5 | 2 | **Low-Medium** |
| `ambient` | Max ambient per player | 15 | 2 | 1 | **Low** - bats. |
| `misc` | Max misc per player | -1 | -1 | -1 | **Low** |

### chunk-settings

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `auto-save-period` | Ticks between auto-saves | -1 (5min) | 12000-36000 | **Medium** - frequent saves = I/O, rare saves = data loss risk |
| `delay-chunk-unloads-by` | Delay chunk unload (ticks) | 300 | 100-300 | **Medium** - prevents thrashing when players move near chunk borders |
| `entity-per-chunk-save-limit` | Max entities per chunk on save | varies | See below | **Low** - prevents chunks from loading with excessive entities |

### entity-per-chunk-save-limit

| Entity Type | Recommended Limit | Reason |
|------------|-------------------|--------|
| `area_effect_cloud` | 8 | Lingering potions |
| `arrow` | 16 | Stray arrows |
| `dragon_fireball` | 3 | Dragon fight |
| `egg` | 8 | Thrown eggs |
| `ender_pearl` | 8 | Thrown pearls |
| `experience_bottle` | 8 | Bottles |
| `fireball` | 8 | Ghast/blaze |
| `firework_rocket` | 8 | Rockets |
| `small_fireball` | 8 | Blaze |
| `snowball` | 8 | Snowballs |
| `tnt` | 50 | TNT dupers, limit lag |
| `item` | 40-100 | Dropped items |
| `falling_block` | 10-20 | Sand/gravel |
| `boat` | 3 | Boats |
| `minecart` | 3 | Minecarts |

### mob-spawn-rate

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `monster` | Ticks between spawn attempts | 1 | 2-4 | **High** - fewer attempts = less CPU, but fewer mobs |
| `animal` | Ticks between spawn attempts | 400 | 400-800 | **Medium** |
| `water-creature` | Ticks between spawn attempts | 400 | 400 | **Low** |
| `water-ambient` | Ticks between spawn attempts | 400 | 800 | **Low** |
| `ambient` | Ticks between spawn attempts | 400 | 800+ | **Low** |

### tracking-range-y

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `enabled` | Enable vertical tracking range | false | true | **Medium** - limits entity tracking vertically, huge savings for tall worlds |
| `animal` | Vertical tracking range | default | 16-32 | Lower = fewer packets for entities above/below |
| `monster` | Vertical tracking range | default | 16-32 | |
| `misc` | Vertical tracking range | default | 8-16 | |
| `player` | Vertical tracking range | default | 48-64 | Keep higher so players see each other |
| `villager` | Vertical tracking range | default | 16 | |

---

## spigot.yml

### entity-activation-range

(Same structure as paper-global.yml but applies when Paper's override is not set. Paper overrides this.)

| Config | What it does | Default | Recommended |
|--------|-------------|---------|-------------|
| `animal` | Animal activation range | 32 | 16-24 |
| `monster` | Monster activation range | 32 | 24 |
| `raid` | Raider activation range | 48 | 32 |
| `misc` | Misc activation range | 16 | 8 |
| `water` | Water mob activation range | 16 | 8 |
| `villager` | Villager activation range | 32 | 16 |

### entity-tracking-range

(Paper overrides this)

| Config | Default | Recommended |
|--------|---------|-------------|
| `player` | 48 | 48-64 |
| `animal` | 48 | 32-48 |
| `monster` | 48 | 48 |
| `misc` | 24 | 16-24 |
| `other` | 48 | 32-48 |

### merge-rum (item merge)

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `item` | Merge radius for items | 2.5 | 3.5-4.0 | **Medium** - larger radius = fewer item entities, less CPU |
| `exp` | Merge radius for XP orbs | 3.0 | 4.0-6.0 | **Medium** - XP orbs are very CPU-heavy in numbers |

### hopper-transfer

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `hopper-transfer` | Ticks between hopper transfers | 8 | 8 (keep default) | **High** - DO NOT set to 1. Use 8. Hoppers are already a top lag source. |
| `hopper-amount` | Items per transfer | 1 | 1 | Keep at 1 to avoid over-taxing the economy. |

### tick-rates

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `mob-spawn` | Mob spawn tick rate | 1 | 1-2 | **Medium** - 2 halves spawn attempts |
| `entity-unlock-dogging` | Unlock entity dogging | N/A | N/A | Unused/removed |
| `sensor` | Sensor tick rates | varies | See below | **High** - controls how often AI sensors fire |

### sensor tick-rates (spigot.yml)

| Sensor | Default | Recommended (Large) | Impact |
|--------|---------|---------------------|--------|
| `nearest-living-entities` | 1 | 4-10 | **Very High** - most frequently called sensor |
| `nearest-player` | 1 | 4-10 | **High** - checked by hostile mobs |
| `player-by-distance` | 1 | 4-10 | **High** |
| `secondary-villager` | 40 | 80-160 | **Medium** - villager activity sensor |
| `villager-babies` | 40 | 80-160 | **Medium** |
| `villager-hostiles` | 40 | 40-80 | **Medium** - villager panic sensor |

---

## bukkit.yml

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `spawn-limits.monsters` | Max monsters per player | 70 | 15-40 | **Very High** - Paper's world config overrides this |
| `spawn-limits.animals` | Max animals per player | 10 | 3-8 | **High** |
| `spawn-limits.water-animals` | Max water mobs per player | 5 | 2-3 | **Medium** |
| `spawn-limits.water-ambient` | Max ambient water mobs per player | 20 | 2-5 | **Medium** |
| `spawn-limits.ambient` | Max ambient per player | 15 | 1 | **Low** |
| `chunk-gc.period-in-ticks` | Chunk GC interval | 600 | 400-600 | **Low** - cleans unloaded chunks from memory |
| `chunk-gc.load-threshold` | Chunks to trigger GC | 0 | 0 | **Low** |
| `aliases` | Command aliases | none | As needed | **None** - convenience only |
| `ticks-per.animal-spawns` | Ticks between animal spawns | 400 | 400-800 | **Medium** |
| `ticks-per.monster-spawns` | Ticks between monster spawns | 1 | 1-4 | **High** |

---

## Folia-Specific Configuration

### Region Threading

| Config | What it does | Default | Notes |
|--------|-------------|---------|-------|
| `region-thread-count` | Number of region threads | auto (cpu-2) | Folia splits world into independent regions that tick in parallel. |
| `io-thread-count` | I/O thread count | auto (cpu/4) | Chunk I/O threads. |
| `max-tick-time` | Max time per tick per region | varies | How long a region can run before it's considered lagging. |

### Parallel Scheduling

| Concept | Description |
|---------|-------------|
| **Region threads** | Each region is an independent area around a player. Separated by > 8 chunks of empty space. |
| **Tick independence** | Each region ticks independently. Lag in one region does not affect another. |
| **Entity tracking** | Entities in different regions are processed by different threads. |
| **Cross-region** | Cross-region operations (portals, etc.) are queued and batched. |

### Folia Performance Notes

- Folia eliminates single-threaded tick bottleneck by parallelizing regions
- Best for servers with 100+ players spread across the world
- Plugins MUST be updated for Folia's API - most plugins are NOT compatible
- Monitor with Spark's region thread view - each region should be independently healthy
- Folia still has a global region for the nether roof, end, and some scheduled tasks

---

## Canvas-Specific Configuration

| Config | What it does | Default | Notes |
|-------- |-------------|---------|-------|
| `branding` | Server brand display | true | Cosmetic. |
| `misc.disable-method-profiling` | Disable method profiling | false | May help performance on some JVMs. |
| `performance.enable-async-chunks` | Async chunk loading | true | Keep enabled for load distribution. |
| `performance.enable-async-mobs` | Async mob spawning | true | Distributes mob spawn calculations. |
| `performance.optimized-dns` | Faster DNS resolution | true | Reduces login delay. |
| `packets.rewrite-all` | Packet rewriting | true | Canvas packet optimization. |

Canvas is a less common fork. Its configurations are more experimental. For production, prefer Paper or Folia.

---

## Quick Reference: Recommended Configs by Scale

### Small Server (< 20 players, 8GB RAM)

```yaml
# server.properties
view-distance: 7
simulation-distance: 4
network-compression-threshold: 256

# paper-global.yml
entity-activation-range: { animals: 24, monsters: 24, misc: 8, water: 12, villagers: 20 }

# paper-world.yml
spawn-limits: { monster: 50, animal: 8, water: 3 }
mob-spawn-rate: { monster: 2 }
```

### Medium Server (20-60 players, 16GB RAM)

```yaml
# server.properties
view-distance: 5-7
simulation-distance: 4
network-compression-threshold: 256

# paper-global.yml
entity-activation-range: { animals: 16, monsters: 20, misc: 6, water: 8, villagers: 16 }

# paper-world.yml
spawn-limits: { monster: 30, animal: 5, water: 2 }
mob-spawn-rate: { monster: 3 }
```

### Large Server (60+ players, 24-32GB RAM)

```yaml
# server.properties
view-distance: 4-5
simulation-distance: 4
network-compression-threshold: 512

# paper-global.yml
entity-activation-range: { animals: 12, monsters: 16, misc: 4, water: 4, villagers: 12 }

# paper-world.yml
spawn-limits: { monster: 15-25, animal: 3, water: 2 }
mob-spawn-rate: { monster: 4 }
entity-per-chunk-save-limit: { item: 40, falling_block: 10 }
```