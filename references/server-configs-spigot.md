# Spigot/Bukkit Configuration Reference

Comprehensive reference for Spigot and Bukkit server configurations with performance focus.

---

## server.properties (Spigot)

| Config | What it does | Default | Recommended | Performance Impact |
|--------|-------------|---------|-------------|-------------------|
| `view-distance` | Chunks sent and ticked around players | 10 | 4-7 | **Very High** - each increment adds ~289 chunks per player (17x17 to 15x15). Directly controls both ticking and rendering in Spigot. |
| `simulation-distance` | — | — | N/A on Spigot | Not available in Spigot (Paper-only). view-distance controls both. |
| `network-compression-threshold` | Packet compression threshold (bytes) | 256 | 256 | **Medium** - lower = more CPU, less bandwidth. -1 = no compression (LAN). 512 for large servers with good bandwidth. |
| `online-mode` | Mojang authentication | true | true | **Low** - only affects login. Set false only for BungeeCord/Velocity setup. |
| `max-players` | Max displayed player count | 20 | As needed | **None** - cosmetic only, does NOT limit connections. |
| `max-tick-time` | Max MSPT before watchdog kills server | 60000 | 60000-120000 | **None** - safety net. Lower = faster crash detection. Increase if legitimate long saves occur. |
| `enable-command-block` | Allow command blocks | true | false if unused | **Low** - command blocks executing every tick can cause lag. |
| `enable-query` | Enable query protocol | false | false | **Low** - slight network overhead if enabled. |
| `enable-rcon` | Enable remote console | false | false | **Low** - attack surface if enabled. |
| `snooper-enabled` | Send usage stats | true | false | **None** - privacy concern, no perf impact. |
| `gamemode` | Default gamemode | survival | As needed | **None** |
| `allow-nether` | Enable nether | true | true | **High if disabled** - prevents nether chunk loading entirely. Trade-off: gameplay vs performance. |
| `spawn-protection` | Spawn protection radius | 16 | 0-16 | **None** - only affects block break/place near spawn. |
| `max-world-size` | World border | 29999984 | Set via /worldborder | **None** - only caps world size. Use worldborder for performance. |
| `rate-limit` | Packets/sec per player | 0 (off) | 500-1000 | **Low** - prevents some client abuse. |

---

## spigot.yml

### Top-level settings

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `debug` | Debug logging | false | false | **None** - verbose logging when true. |
| `log-villager-deaths` | Log villager deaths | true | false | **None** - reduces log spam. |
| `log-named-deaths` | Log named entity deaths | true | false | **None** - reduces log spam. |
| `sample-count` |tps sample count | 12 | 12 | **None** - TPS averaging window. |

### world-settings (per-world)

#### entity-activation-range

Controls how close a player must be for entities to start ticking. Entities outside this range are "frozen" - they don't move, pathfind, or process AI. **This is the single most impactful Spigot performance setting.**

| Config | What it does | Default | Small (<20) | Medium (20-60) | Large (60+) | Impact |
|--------|-------------|---------|-------------|----------------|-------------|--------|
| `animal` | Activation range for animals | 32 | 24-32 | 16-24 | 8-16 | **Very High** - fewer active entities = huge CPU savings |
| `monster` | Activation range for monsters | 32 | 28-32 | 24 | 16-24 | **Very High** - monsters need some range for gameplay |
| `raid` | Activation range for raiders | 48 | 32-48 | 32 | 24 | **High** - raid entities |
| `misc` | Activation range for misc | 16 | 12-16 | 8 | 4-8 | **High** - items, XP, boats, arrows |
| `water` | Activation range for water mobs | 16 | 12-16 | 8-12 | 4-8 | **High** - squid, fish |
| `villager` | Activation range for villagers | 32 | 24-32 | 16-24 | 12-16 | **Very High** - villagers are extremely CPU-heavy (pathfinding, schedules, breeding) |
| `flying-monster` | Activation range for flying | 32 | 32 | 24-32 | 16-24 | **High** - phantoms |

**Note**: If Paper is installed, Paper's `paper-global.yml` overrides these values.

#### entity-tracking-range

Controls how far away entities are visible (sent to clients). Does NOT affect ticking - purely visual.

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `player` | Player visibility range | 48 | 48-64 | **Low** - packet sending only |
| `animal` | Animal visibility range | 48 | 32-48 | **Low** - visual pop-in below 32 |
| `monster` | Monster visibility range | 48 | 48 | **Low** - gameplay concern if too low |
| `misc` | Misc entity visibility | 24 | 16-24 | **Low** - items don't need far visibility |
| `other` | Other entity visibility | 48 | 48 | **Low** |

#### merge-rum (item merging)

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `item` | Radius for item merge (blocks) | 2.5 | 3.5-4.0 | **High** - more merging = fewer item entities = less CPU. Especially important for farms. |
| `exp` | Radius for XP orb merge (blocks) | 3.0 | 4.0-6.0 | **High** - XP orbs are very CPU-intensive in large numbers. Aggressive merging recommended. |

#### hopper-transfer

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `hopper-transfer` | Ticks between hopper transfers | 8 | 8 | **Very High** - NEVER set to 1. Hoppers already consume significant tick time. 8 is balanced. |
| `hopper-amount` | Items transferred per hopper tick | 1 | 1 | **High** - increasing this changes game balance significantly. Keep at 1. |
| `hopper-check` | Ticks between hopper neighbor checks | 1 | 1 | **High** - how often hoppers check for items above. 1 is the minimum (every tick). |

**Important**: On Spigot, hoppers are a top-3 lag source. The 8-tick transfer rate is already a compromise. Reducing it to 1 creates massive performance problems. Instead, reduce hopper count in your builds.

#### mob-spawn-range

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `mob-spawn-range` | Chunk range for mob spawning | 8 | 4-6 | **High** - Should be <= view-distance. Controls where mobs can spawn relative to players. |

#### growth / ticks-per

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `cactus-growth-modifier` | Cactus growth speed % | 100 | 100 | **Low** - growth ticks are lightweight |
| `cane-growth-modifier` | Sugar cane growth % | 100 | 100 | **Low** |
| `melon-growth-modifier` | Melon growth % | 100 | 100 | **Low** |
| `pumpkin-growth-modifier` | Pumpkin growth % | 100 | 100 | **Low** |
| `wheat-growth-modifier` | Wheat growth % | 100 | 100 | **Low** |
| `mushroom-growth-modifier` | Mushroom growth % | 100 | 100 | **Low** |
| `vine-growth-modifier` | Vine growth % | 100 | 0-100 | **Low** - vines can spread excessively in jungles |
| `ticks-per.hopper-transfer` | Alias for hopper-transfer | 8 | 8 | Same as hopper-transfer above |

#### arrow-despawn-rate

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `arrow-despawn-rate` | Ticks before arrows despawn | 1200 | 60-200 | **Medium** - arrows in the ground are ticking entities. Lowers entity count on PvP servers. |

#### zombie-aggressive-toward-villager

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `zombie-aggressive-toward-villager` | Zombies target villagers | true | false (large) | **High** - zombie villager targeting creates pathfinding load. Disable on servers without village gameplay. |

#### nerf-spawner-mobs

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `nerf-spawner-mobs` | Spawner mobs have no AI | false | true (large) | **High** - spawner mobs with no AI use almost no CPU. They don't move or attack. Good for mob farms. |

---

## bukkit.yml

### spawn-limits

These set the maximum number of each mob type per player. **Multiplicative in Spigot**: a server with `spawn-limits.monsters: 70` and 10 players allows up to 700 monsters globally.

| Config | What it does | Default | Small | Medium | Large | Impact |
|--------|-------------|---------|-------|--------|-------|--------|
| `monsters` | Max monsters per player | 70 | 40-50 | 20-40 | 10-20 | **Very High** - most impactful setting for entity lag |
| `animals` | Max animals per player | 10 | 6-10 | 4-6 | 2-4 | **High** - animals are heavy due to pathfinding/breeding |
| `water-animals` | Max water mobs per player | 5 | 3 | 2-3 | 1-2 | **Medium** - squid, dolphins |
| `water-ambient` | Max water ambient per player | 20 | 5 | 2-5 | 1-2 | **Medium** - fish, lots of ambient = load |
| `ambient` | Max ambient per player | 15 | 1-2 | 1 | 1 | **Low** - bats only |

### ticks-per

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `animal-spawns` | Ticks between animal spawn attempts | 400 | 400-600 | **Medium** - lower spawn frequency = fewer spawn cycle CPU spikes |
| `monster-spawns` | Ticks between monster spawn attempts | 1 | 1-2 | **High** - 2 halves spawn attempts (and resulting mob count) |
| `water-spawns` | Ticks between water mob spawn attempts | 1 | 1-5 | **Medium** |
| `water-ambient-spawns` | Ticks between water ambient spawns | 1 | 5-10 | **Low** |
| `ambient-spawns` | Ticks between ambient spawns | 1 | 10+ | **Low** - bats |

### chunk-gc

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `period-in-ticks` | Interval between chunk GC | 600 | 400-600 | **Low** - removes orphaned chunks from memory |
| `load-threshold` | Chunk count to trigger GC | 0 | 0 | **None** - 0 means only time-based GC |

### aliases

| Config | What it does | Default | Impact |
|--------|-------------|---------|--------|
| `aliases` | Command alias mapping | empty | **None** - convenience only for commands |

---

## Quick Sizing Guide

### Small Server (< 20 players, 6-8GB)

```yaml
# server.properties
view-distance: 7
network-compression-threshold: 256

# spigot.yml
entity-activation-range: { animal: 28, monster: 28, misc: 12, water: 12, villager: 24 }
merge-rum: { item: 3.0, exp: 4.0 }

# bukkit.yml
spawn-limits: { monsters: 50, animals: 8, water-animals: 3, ambient: 2 }
ticks-per: { monster-spawns: 1, animal-spawns: 400 }
```

### Medium Server (20-60 players, 12-16GB)

```yaml
# server.properties
view-distance: 5-6
network-compression-threshold: 256

# spigot.yml
entity-activation-range: { animal: 20, monster: 24, misc: 8, water: 8, villager: 16 }
merge-rum: { item: 3.5, exp: 5.0 }

# bukkit.yml
spawn-limits: { monsters: 30, animals: 5, water-animals: 2, ambient: 1 }
ticks-per: { monster-spawns: 2, animal-spawns: 500 }
```

### Large Server (60+ players, 24GB+)

```yaml
# server.properties
view-distance: 4-5
network-compression-threshold: 512

# spigot.yml
entity-activation-range: { animal: 12, monster: 20, misc: 6, water: 4, villager: 12 }
merge-rum: { item: 4.0, exp: 6.0 }
nerf-spawner-mobs: true
arrow-despawn-rate: 60

# bukkit.yml
spawn-limits: { monsters: 15, animals: 3, water-animals: 1, ambient: 1 }
ticks-per: { monster-spawns: 3, animal-spawns: 600 }
```

---

## Common Misconfigurations

| Misconfiguration | Problem | Fix |
|-----------------|---------|-----|
| view-distance > 8 | Massive chunk ticking load with diminishing returns | Set to 4-7 |
| spawn-limits unchanged from default | 70 monsters per player scales terribly | Lower to 15-40 |
| entity-activation-range at 32 | Far too many entities ticking | Lower to 16-24 |
| hopper-transfer = 1 | Hoppers become #1 lag source | Keep at 8 |
| merge-rum.item at default 2.5 | Too many individual item entities | Increase to 3.5-4 |
| No arrow-despawn-rate tuning | Arrows accumulate after PvP | Set to 60-200 |
| mob-spawn-range > view-distance | Spawning in unloaded chunks = wasted cycles | Keep <= view-distance |
| zombie-aggressive-toward-villager = true on non-village servers | Unnecessary pathfinding | Set false |