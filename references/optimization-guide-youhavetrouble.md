# YouHaveTrouble's Minecraft Server Optimization Guide

> Reference extracted from YouHaveTrouble/minecraft-optimization (branch `1.21.11`, MC 1.21.11).
> Source: https://github.com/YouHaveTrouble/minecraft-optimization
> Companion pitfalls doc: https://github.com/YouHaveTrouble/minecraft-optimization/blob/1.21.11/common-pitfalls-and-best-practices.md

A community-maintained, version-tagged guide. Complements Paper Chan's guide with more granular per-option rationale, Purpur-specific tweaks, and "too good to be true" plugin warnings. Values below are good *starting points* for an SMP-like server -- always adjust for gamemode and player count.

---

## Table of Contents

1. [Preparations](#preparations)
2. [Networking](#networking)
3. [Chunks](#chunks)
4. [Mobs](#mobs)
5. [Misc](#misc)
6. [Helpers](#helpers)
7. [Java Startup Flags](#java-startup-flags)
8. ["Too good to be true" plugins](#too-good-to-be-true-plugins)
9. [Measuring Performance](#measuring-performance)
10. [Common Pitfalls & Best Practices](#common-pitfalls--best-practices)

---

## Preparations

### Server JAR

**Recommended:**
- **Paper** -- most popular, performance + gameplay/mechanics fixes.
- **Purpur** -- Paper fork focused on features and customization freedom.

**Avoid:**
- Paid JARs claiming async anything -- 99.99% scams.
- Bukkit/CraftBukkit/Spigot -- outdated performance vs alternatives.
- Anything that enables/disables/reloads plugins at runtime (see `/reload` problem).
- Many forks further downstream from Paper/Purpur -- instability risk. Prefer optimizing your server or investing in a private fork.

### Map pregen

Pregeneration is now mostly useful on terrible/single-threaded/limited CPUs, though still commonly used for world-map plugins (Pl3xMap, Dynmap).

- Use **Chunky** to pregen; **set a vanilla world border** (`/worldborder set [diameter]`) -- overworld, nether, and end each need their own border (nether is 8x smaller by default).
- Vanilla world border also limits treasure-map lookup range, which can cause lag spikes -- set it even if you don't pregen.

> Paper and above: chunk loading won't affect TPS, but chunk *load speed* slows down when the CPU is overloaded.

---

## Networking

### server.properties

#### network-compression-threshold
`Good starting value: 256`

Cap (bytes) before the server attempts packet compression. Higher = saves CPU at bandwidth cost and can hurt slow-connection clients. `-1` disables. With a proxy or co-located backend (<2 ms ping), disabling (`-1`) is beneficial since LAN/internal speeds handle uncompressed traffic.

### purpur.yml

#### use-alternate-keepalive
`Good starting value: true`

Sends a keepalive packet once per second; only kicks if **none** of them are answered in 30 seconds. Helps players with flaky connections. Known incompatibility with TCPShield.

---

## Chunks

### server.properties

#### simulation-distance
`Good starting value: 4`

Distance (chunks) around the player the server **ticks** (furnaces, crop growth, etc.). Intentionally set low (`3` or `4`) because `view-distance` lets players see further without ticking.

#### view-distance
`Good starting value: 7`

Distance (chunks) **sent** to players (no-tick view distance equivalent). Total view distance = `max(view-distance, simulation-distance)`. e.g. sim=4, view=12 -> client sees 12 chunks.

### spigot.yml

#### view-distance
`Good starting value: default`

Overwrites `server.properties` if not `default`. Keep `default` to manage both sim/view in one place.

### paper-world configuration

#### delay-chunk-unloads-by
`Good starting value: 10s`

How long chunks stay loaded after a player leaves. Prevents constant load/unload churn on back-and-forth movement. Too high = too many chunks loaded. For frequently-teleported areas, consider permanent loading.

#### prevent-moving-into-unloaded-chunks
`Good starting value: true`

Stops players from moving into unloaded chunks, preventing sync main-thread loads. More impactful the lower your `view-distance` is.

#### entity-per-chunk-save-limit

```
Good starting values:
  area_effect_cloud: 8
  arrow: 16
  breeze_wind_charge: 8
  dragon_fireball: 3
  egg: 8
  ender_pearl: 8
  experience_bottle: 3
  experience_orb: 16
  eye_of_ender: 8
  fireball: 8
  firework_rocket: 8
  llama_spit: 3
  splash_potion: 8
  lingering_potion: 8
  shulker_bullet: 8
  small_fireball: 8
  snowball: 8
  spectral_arrow: 16
  trident: 16
  wind_charge: 8
  wither_skull: 4
```

Limits how many of a given entity type can be saved per chunk. Provide a limit for **every projectile** at minimum to avoid save/load crashes from projectile pile-ups. Adjust per gamemode. Not designed to prevent legitimate large mob farms.

---

## Mobs

### bukkit.yml

#### spawn-limits

```
Good starting values:
  monsters: 20
  animals: 5
  water-animals: 2
  water-ambient: 2
  water-underground-creature: 3
  axolotls: 3
  ambient: 1
```

Formula: `[playercount] * [limit]`. Smaller = fewer mobs. `per-player-mob-spawn` adds an equal-distribution limit. Lowering is double-edged -- reduces server work but cuts gameplay mobs. Can go as low as ~20 if `mob-spawn-range` is tuned. On Paper you can set per-world limits in paper-world config.

#### ticks-per

```
Good starting values:
  monster-spawns: 10
  animal-spawns: 400
  water-spawns: 400
  water-ambient-spawns: 400
  water-underground-creature-spawns: 400
  axolotl-spawns: 400
  ambient-spawns: 400
```

How often (ticks) the server attempts to spawn entities. Water/ambient mobs don't die fast -- raising intervals barely affects spawn rates. Monsters: slightly increasing shouldn't hurt mob-farm rates. All values should typically be `> 1`.

### spigot.yml

#### mob-spawn-range
`Good starting value: 3`

Range (chunks) around the player where mobs spawn. Lowering makes it feel like more mobs surround each player. Should be `<= simulation-distance` and `<= hard despawn range / 16`.

#### entity-activation-range

```
Good starting values:
  animals: 16
  monsters: 24
  raiders: 48
  misc: 8
  water: 8
  villagers: 16
  flying-monsters: 48
```

Distance from player at which an entity ticks. Lowering helps performance but mobs become unresponsive until the player is close. Too low breaks farms -- iron farms are the most common victim.

#### entity-tracking-range

```
Good starting values:
  players: 48
  animals: 48
  monsters: 48
  misc: 32
  other: 64
```

Distance (blocks) at which entities are visible (just not sent to clients). Too low = mobs appear to pop in. Generally should be higher than `entity-activation-range`.

#### tick-inactive-villagers
`Good starting value: false`

Whether villagers tick outside activation range. `false` improves performance but can confuse players, can break iron farms, and can interfere with trade restocking.

#### nerf-spawner-mobs
`Good starting value: true`

Mobs from monster spawners get no AI. Nerfed mobs do nothing. Pair with `spawner-nerfed-mobs-should-jump: true` (paper-world) to let them jump in water.

### paper-world configuration

#### despawn-ranges

```
Good starting values (per category):
  ambient / axolotls / creature / misc / monster /
  underground_water_creature / water_ambient / water_creature:
    hard: 72
    soft: 30
```

Despawn ranges (blocks). Lower to clear distant mobs faster. Keep **soft ~30** and set **hard** a bit above your simulation distance: `(simulation-distance * 16) + 8`. Hard = instant despawn; between soft/hard = random chance of despawn. Hard must be > soft.

#### per-player-mob-spawns
`Good starting value: true`

Mob spawns account for mobs already around each player. Fixes inconsistent spawns caused by farm-saturated mobcaps and lets you set lower `spawn-limits`. Slight perf cost, dwarfed by the spawn-limit savings it enables. More singleplayer-like spawning.

#### max-entity-collisions
`Good starting value: 2`

How many collisions one entity processes at once. `0` = can't push anything (including players). `2` usually enough. Renders `maxEntityCramming` gamerule useless if set above this value.

> Cross-reference with `server-config-review.md`: **never set below 3** for gameplay-affecting worlds -- mobs jamming through each other breaks cramming-based mechanics.

#### update-pathfinding-on-block-update
`Good starting value: false`

Disabling reduces pathfinding work for perf gain. Mobs may appear laggier -- they passively update paths every 5 ticks (0.25s).

#### fix-climbing-bypassing-cramming-rule
`Good starting value: true`

Stops mobs (spiders) from evading cramming while climbing. Prevents absurd stacking in tight vertical spaces.

#### armor-stands.tick
`Good starting value: false`

Disable unless you use plugins that modify armor stand behavior or notice issues. Off = armor stands not pushed by water/gravity.

#### armor-stands.do-collision-entity-lookups
`Good starting value: false`

Disable armor stand collisions. Helps when many armor stands exist and don't need collision.

#### tick-rates

```
Good starting values:
  behavior.villager:
    validatenearbypoi: 60
    acquirepoi: 120
  sensor.villager:
    secondarypoisensor: 80
    nearestbedsensor: 80
    villagerbabiessensor: 40
    playersensor: 40
    nearestlivingentitysensor: 40
```

How often behaviors/sensors fire (ticks). `acquirepoi` is the heaviest villager behavior -- greatly increased. Lower again if villagers fail to pathfind.

### purpur.yml

#### zombie.aggressive-towards-villager-when-lagging
`Good starting value: false`

Stops zombies targeting villagers when TPS falls below `lagging-threshold`.

#### entities-can-use-portals
`Good starting value: false`

Disables portal use for all non-player entities. Prevents cross-world chunk loads (main-thread). Side effect: entities can't traverse portals.

#### villager.lobotomize.enabled
`Good starting value: true`

> Only enable if villagers are causing lag -- otherwise the pathfinding checks may hurt perf.

Strips AI from villagers that can't pathfind to destination; they just restock periodically. Freeing them un-lobotomizes.

#### villager.search-radius

```
Good starting values:
  acquire-poi: 16
  nearest-bed-sensor: 16
```

Radius in which villagers search for job-site/bed blocks. Big perf boost with many villagers, but blocks beyond the radius are undetectable.

---

## Misc

### spigot.yml

#### merge-radius

```
Good starting values:
  item: 3.5
  exp: 4.0
```

Distance (blocks) for item/xp merging -- reduces ground-tick count. Too high = items/xp appear to vanish and can teleport through walls (unless Paper's `fix-items-merging-through-walls`). XP only merges on creation.

> Cross-ref `server-config-review.md`: excessive `merge-radius` is a **bug-config** -- items visibly teleport.

#### hopper-transfer
`Good starting value: 8`

Ticks hoppers wait to move an item. Higher helps perf on hopper-heavy servers but breaks hopper clocks and possibly item sorters.

> **NEVER set to 1.** Keep at 8. Setting lower is server-destroying -- see `server-config-review.md` bug-config warnings.

#### hopper-check
`Good starting value: 8`

Ticks between hopper checks for items above/in the inventory above. Higher helps perf but breaks hopper clocks and water-stream sorters.

### paper-world configuration

#### alt-item-despawn-rate

```
Good starting values:
  enabled: true
  items:
    cobblestone: 300
    netherrack: 300
    sand: 300
    red_sand: 300
    gravel: 300
    dirt: 300
    short_grass: 300
    pumpkin: 300
    melon_slice: 300
    kelp: 300
    bamboo: 300
    sugar_cane: 300
    twisting_vines: 300
    weeping_vines: 300
    oak_leaves: 300
    spruce_leaves: 300
    birch_leaves: 300
    jungle_leaves: 300
    acacia_leaves: 300
    dark_oak_leaves: 300
    mangrove_leaves: 300
    cherry_leaves: 300
    cactus: 300
    diorite: 300
    granite: 300
    andesite: 300
    scaffolding: 600
```

Alternative despawn delay (ticks) for specific dropped items. Replaces item-clearing plugins alongside `merge-radius`.

#### redstone-implementation
`Good starting value: ALTERNATE_CURRENT`

Faster alternative redstone impl that cuts redundant block updates. Based on the [Alternate Current](https://modrinth.com/mod/alternate-current) mod. May introduce minor edge-case inconsistencies with very technical redstone; gains outweigh niche issues. A non-vanilla impl can also fix CraftBukkit-induced inconsistencies.

#### hopper.disable-move-event
`Good starting value: false`

`InventoryMoveItemEvent` only fires if a plugin listens. Only set `true` if you have such a plugin and don't need it acting. **Do NOT enable if you use protection plugins that listen to this event.**

#### hopper.ignore-occluding-blocks
`Good starting value: true`

Whether hoppers ignore containers inside full blocks (e.g. hopper minecart in sand). Enabling breaks contraptions relying on that behavior.

#### tick-rates.mob-spawner
`Good starting value: 2`

How often spawners tick. Higher = less lag with many spawners, but too high (vs spawner delay) cuts spawn rates.

#### optimize-explosions
`Good starting value: true`

Faster explosion algorithm with slight damage calc inaccuracy -- usually unnoticeable.

#### treasure-maps.enabled
`Good starting value: false`

Treasure-map generation is extremely expensive and can hang the server if the target structure is in an ungenerated chunk. Safe to enable only with a pregenerated world **and** a vanilla world border.

#### treasure-maps.find-already-discovered

```
Good starting values:
  loot-tables: true
  villager-trade: true
```

Default forces new maps toward unexplored structures (usually ungenerated chunks). Setting `true` lets maps lead to already-discovered structures, avoiding hangs/crashes. `villager-trade` = villager-sold maps; `loot-tables` = dynamic loot (treasure/dungeon chests, etc.).

#### tick-rates.grass-spread
`Good starting value: 4`

Ticks between grass/mycelium spread attempts. Slows terrain conversion slightly; `4` is barely noticeable.

#### tick-rates.container-update
`Good starting value: 1`

Ticks between container updates. Raising may help rare container-update issues but increases ghost-item desync risk.

#### non-player-arrow-despawn-rate
`Good starting value: 20`

Ticks before mob-shot arrows despawn after hitting. Players can't pick these up anyway -- 20 (1s) is fine.

#### creative-arrow-despawn-rate
`Good starting value: 20`

Same, for creative-mode player arrows.

### purpur.yml

#### dolphin.disable-treasure-searching
`Good starting value: true`

Prevents dolphins running structure search similar to treasure maps.

#### teleport-if-outside-border
`Good starting value: true`

Teleports player to world spawn if outside the (bypassable) vanilla world border, mitigating its damage.

---

## Helpers

### paper-world configuration

#### anti-xray.enabled
`Good starting value: true`

Hides ores from x-rayers. Decreases performance slightly but is much more efficient than any anti-xray plugin; impact usually negligible. Detailed config: https://docs.papermc.io/paper/anti-xray

#### nether-ceiling-void-damage-height
`Good starting value: 127`

If `> 0`, players above this Y take void damage. Prevents nether-roof use. Vanilla nether is 128 tall -> set `127`. Adjust if you've changed nether height.

---

## Java Startup Flags

- MC 1.20.5+ requires **Java 21+**. Oracle licensing makes Adoptium / Amazon Corretto the recommended vendors. Avoid OpenJ9/GraalVM (unsupported by Paper, known issues).
- Use **Aikar's flags** (G1GC) for Minecraft: https://docs.papermc.io/paper/aikars-flags -- do not use on alternative JVMs.
- Use the **flags.sh** generator to get the correct startup flags for your server.

> For the full flag breakdown, cross-reference `references/jvm-gc-tuning.md` and `references/jvm-flags-advanced.md`.

---

## "Too good to be true" plugins

### Plugins removing ground items
Unnecessary -- replaceable with `merge-radius` + `alt-item-despawn-rate`. Item-clearing plugins tend to use **more** resources scanning/removing than not removing at all, and are less configurable.

### Mob stacker plugins
Hard to justify. Stacking **naturally-spawned** entities causes more lag than not stacking -- the server keeps trying to spawn more mobs. Only "acceptable" use case: spawners on servers with many spawners.

### Plugins enabling/disabling other plugins
Dangerous. Enabling a plugin at runtime can cause fatal errors with tracking data; disabling can break dependencies. `/reload` has the same problems -- see me4502's blog post: https://madelinemiller.dev/blog/problem-with-reload/

---

## Measuring Performance

### mspt
Paper's `/mspt` command. First two values < 50 ms = server not lagging. Third value (max) > 50 occasionally is normal -- don't panic.

### Spark
**Spark** (https://spark.lucko.me/) profiles CPU/memory. Wiki: https://spark.lucko.me/docs/ -- lag-spike guide: https://spark.lucko.me/docs/guides/Finding-lag-spikes

> This is the tool the rest of this skill analyzes. Use `/spark profiler`/`heapsummary`/`health` to collect the data, then run `spark_toolkit.py` commands.

---

## Common Pitfalls & Best Practices

From the companion `common-pitfalls-and-best-practices.md`:

- **Always back up.** There are those who make backups and those who will start. Worlds and plugin data can be lost -- it's just a matter of time.
- **Don't run outdated software.** Risks unpatched dupes/exploits and forces client downgrades (or protocol hacks).
- **Don't run Bukkit/Spigot anymore.** Maintenance-mode only -- no perf updates. Upgrade to Paper or Purpur; Bukkit/Spigot plugins work there.
- **Avoid shared hosting if possible.** Guaranteed resources are tiny; shared resources are oversold and rarely fully usable.
- **Avoid datapacks that run command functions.** Scale poorly with player count -- use plugin alternatives. Datapacks modifying biomes/loot tables are fine.
- **Choose hardware by CPU, not just RAM.** Single-core performance matters most (https://www.cpubenchmark.net/singleThread.html). Avoid HDDs -- MC is I/O heavy; use SSD.