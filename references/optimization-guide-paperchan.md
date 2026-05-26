# Paper Chan's Little Guide to Minecraft Server Optimization

> Comprehensive reference extracted from Paper Chan's guide (Last updated: May 23rd, 2026 for Paper Version 26.1.2 Build #65)
> Source: https://paper-chan.moe/paper-optimization/

---

## Table of Contents

1. [Core Philosophy](#core-philosophy)
2. [Pre-generation (Chunky)](#pre-generation-chunky)
3. [View Distance & Simulation Distance](#view-distance--simulation-distance)
4. [Entity Count Control](#entity-count-control)
5. [Understanding Mob Spawn Mechanics](#understanding-mob-spawn-mechanics)
6. [server.properties](#serverproperties)
7. [bukkit.yml](#bukkiyml)
8. [spigot.yml](#spigotyml)
9. [Paper World Defaults](#paper-world-defaults)
10. [Paper Global Settings](#paper-global-settings)
11. [Per-World Config](#per-world-config)
12. [JVM Flags](#jvm-flags)
13. [Common Mistakes](#common-mistakes)
14. [Things to Avoid](#things-to-avoid)
15. [Quality of Life Plugins & Tools](#quality-of-life-plugins--tools)

---

## Core Philosophy

**There is no singular setup that will work for every server.** You should read and understand each available config option and tweak the numbers accordingly to fit your own unique circumstances. The optimal config for your server will vary based on server hardware, average player count, and the type of game mode running.

As your world ages and players progress into late game, the workload on the server gradually increases over time so server optimizing is not a one-off task but a continuous effort.

> There is only so much you can take out of a car to make it go faster until you are left with nothing but a steering wheel and a bare chassis, the same applies to optimizing your server.

---

## Pre-generation (Chunky)

Generating new chunks consumes a considerable amount of resources. It is recommended to pre-generate your map if you are launching a new map/server.

Even if you do not plan to set a world border, it is still a good idea to pre-generate `5~10k` from your spawn as it will help ease the launch day stress. Not to mention, it will catch any potential uncaught bugs on generation ahead of the actual launch day.

**Tools:**
- [Chunky](https://hangar.papermc.io/pop4959/Chunky) — simplest pre-gen plugin
- [ChunkyBorder](https://modrinth.com/plugin/chunkyborder) — customize border shapes

> Be reasonable when picking a border — the file size will grow exponentially the further you set the border and this may cause issues with storage and backup later on.

---

## View Distance & Simulation Distance

**Definitions:**
- `simulation-distance` — determines how much environment is **active (ticking)** around the player. **Huge impact on performance.** Default is 10.
- `view-distance` — determines how many **chunks (terrain) are visible** to the player. Less performance heavy but occupies more RAM.

**Rules:**
- `simulation-distance` should always be **equal to or lower than** `view-distance`. (If simulation distance is set higher than view distance, only an area up to view distance will be applied)
- It is strongly discouraged to reduce these values lower than `5`.
- Most YouTube farm designs are made based on a simulation distance of 10. Lower this value will impact those farms.

**Chunk count formula:**

```
Total chunks loaded per player = [(View Distance + 2) × 2 + 1]²
```

| view-distance | Chunks per Player |
|---------------|-------------------|
| 5             | 225               |
| 10 (Vanilla)  | 625               |
| 15            | 1,225             |

Each additional increase after 10 causes exponential growth in loaded chunks. Although `view-distance` uses significantly less resources compared to `simulation-distance`, still be mindful of its performance impact.

You can define individual values on a per-world basis in `spigot.yml` to overwrite `server.properties`. For example, set a higher `view-distance` in `the_end` dimension for better Elytra navigation.

> Encourage players to install Fabric mod loaders with client mods such as Bobby or Farsight to cache chunk views locally with no cost to server performance!

---

## Entity Count Control

Entities are resource-intensive in Modern Minecraft versions — even top-of-the-line CPUs can be brought down to their knees if you do not keep entities under control.

**Target:** Maintain overall entity ticks to **less than 30%** (assuming reasonable player activity, not an empty server). Use [spark](https://spark.lucko.me/) to find the source of lags and compare optimization results.

Ideally, you want to get your mob density as close to Vanilla as possible while maintaining **below 50 mspt on average during peak hours**.

---

## Understanding Mob Spawn Mechanics

### Spawn Ranges Visual Diagram

The graph and indicated values are based on Vanilla/Paper defaults:

- **Brown cylinders** — mob spawn range
- **Red sphere** — mob spawning zone (between 24–128 blocks)
- **Yellow sphere** — mob free zone (no mobs spawn within 24 blocks of a player)
- Entities within **32 blocks** (entity activation range) — ticked at normal rate
- Entities between **32–128 blocks** — ticked at reduced rate
- Any entity **outside 128 blocks** — instantly despawned

### Vanilla / Paper Default Values

| Setting                | Default Value |
|------------------------|---------------|
| View Distance          | 10 (chunks)   |
| Simulation Distance    | 10 (chunks)   |
| Mob Spawn Range         | 8 (chunks)    |
| Despawn Range (soft)   | 32 (blocks)   |
| Despawn Range (hard)    | 128 (blocks)  |
| Entity Activation Range | 32 (blocks)  |

These 5 config options are closely related to each other — it is crucial to ensure each value is set up correctly.

### How the Ranges Relate

**`simulation-distance`** determines the maximum possible size of a farm:

- A farm **cannot exceed** the radius of `(simulation distance - 1) × 16` blocks
- Everything outside of simulation distance won't tick, so any farm bigger than this won't be functional

**`mob-spawn-range`** also determines the maximum size of a farm:

- Should be between `(simulation distance - 1)` to `3` minimum
- If running vanilla default simulation distance of 10, keep mob spawn range at 8 or lower
- Mobs can only spawn a minimum of `24 blocks` away from players, so setting mob spawn range below `3` is strongly discouraged unless simulation distance is extremely low (3 or lower)
- Every mob farm has a designated mob collection platform — the size of the platform is determined solely by this value (in chunks)

**`despawn-range`** (both hard and soft) governs the despawn behavior of non-persistent entities:

- Entities within `soft despawn range` have a predetermined chance to despawn — helps rotate entity variety
- Non-persistent entities **instantly despawn** if outside `hard despawn range`
- Paper offers server owners the option to adjust despawn range both **horizontally and vertically**

> Any alteration to the settings above requires you to adjust the farm's overall size and its designated AFK spot accordingly.

### Diagnostic Commands

- `/paper mobcaps` — global mobcaps and total spawnable chunks
- `/paper playermobcaps` — player mobcaps

Especially useful for finding errors on spawnproofing. If no mobs are spawning inside the farm while the mobcap is full, it means you have failed spawn-proofing.

### Why Farms Built in Older Versions May Be Slower

Minecraft runs spawn checks between the lowest block and the highest block to check if a block is eligible for a spawn attempt, then has a 24% chance to succeed at spawning at that particular Y position.

With the world height change (Y-64 to Y320 instead of Y0 to Y265), your farm from 1.17 located on Y0 now has 64 more additional blocks below it, which slows down mob spawning.

**Mitigation:**
1. Rebuild your farm at the lowest possible Y level (Y-64) — most ideal but most painful
2. Dig out an even larger perimeter & empty out everything below the farm from Y-64 to Y0 (air block only)
3. Accept that mob spawning is inherently flawed in multiplayer servers

> TL;DR The most effective farm location is at the lowest possible Y level with only air block above.

---

## server.properties

### view-distance & simulation-distance

```properties
view-distance=10
simulation-distance=10
```

- `view-distance` sets the **view distance (terrain only)** unless stated otherwise in `spigot.yml`
- `simulation-distance` sets the **simulation distance (ticking)** unless stated otherwise in `spigot.yml`
- See [View Distance section](#view-distance--simulation-distance) for chunk count formula and picking guidance

### allow-flight

```properties
allow-flight=true
```

Prevents players from getting kicked by the server for "flying" while riding a horse or climbing on scaffolding. Having this as `true` doesn't mean everyone can fly — it just means players won't get kicked if the server thinks they are flying.

### log-ips

```properties
log-ips=true
```

Vanilla Minecraft provides an option to toggle player IP address logging. Set to `false` to protect player privacy, especially useful when log files need to be shared with third parties for troubleshooting.

### pause-when-empty-seconds

```properties
pause-when-empty-seconds=-1
```

Mojang introduced a pause feature that puts the server into sleep mode when no players are online. This is very likely to cause issues with servers that have plugins. Default `-1` means disabled.

---

## bukkit.yml

### spawn-limits

```yaml
spawn-limits:
  monsters: 70
  animals: 10
  water-animals: 5
  water-ambient: 20
  water-underground-creature: 5
  axolotls: 5
  ambient: 15
```

This determines the mob cap in your server. Lowering the value here has the most direct impact on server performance, as entities are one of the most resource intensive tasks.

The global entity cap will **scale based on online player counts** as long as `per-player-mob-spawns` is set to `true` in `paper-world-defaults.yml`.

#### Spawn-Limit Cheat Sheet (Monster Category)

To maintain **perceived mob density** consistent with Vanilla default, also alter `mob-spawn-range` in spigot.yml.

**Mob density math:**

```
(Default mob Cap) : (Default Spawn Area) = (New Mob Cap) : (New Spawn Area)

Constants:
  Default Mob Spawn Range = 8 chunks
  Minimum distance where a mob can spawn = 24 blocks away from a player

Default Spawn Area = [(Mob Spawn Range × 2 × 16) + 1]² - (24 × 2 + 1)²
                   = (8 × 2 × 16 + 1)² - 49²
                   = 66049 - 2401
                   = 63648

Example: New mob cap = 45
  70 : 63648 = 45 : b
  b = 40916 (New Spawn Area in blocks)

  Let a = New Mob Spawn Range, where b = [(a × 16 × 2) + 1]² - (24 × 2 + 1)²
  (32a + 1)² - 2401 = 40916
  (32a + 1)² = 43317
  32a + 1 = 208
  32a = 207
  a = 6.46 → set mob-spawn-range to 6 (or 7) in spigot.yml
```

#### Spawn-Limit Cheat Sheet Table

| Overall Entity Count | Suggested `spawn-limit` (bukkit.yml) | Suggested `mob-spawn-range` (spigot.yml) | Actual Calculated Number |
|----------------------|---------------------------------------|------------------------------------------|--------------------------|
| 100% (Vanilla)       | 70 (default)                          | 8 (default)                              | 8 (default)              |
| 90%                  | 63                                    | 7 or 8                                   | 7.6                      |
| 80%                  | 56                                    | 7                                        | 7.18                     |
| 70%                  | 49                                    | 6 or 7                                   | 6.74                     |
| 60%                  | 42                                    | 6                                        | 6.26                     |
| 50%                  | 35                                    | 5 or 6                                   | 5.75                     |
| 40%                  | 28                                    | 5                                        | 5.18                     |
| 30%                  | 21                                    | 4 or 5                                   | 4.55                     |
| 20%                  | 14                                    | 4                                        | 3.81                     |
| 10%                  | 7                                     | 3                                        | 2.89                     |
| 3%                   | 2                                     | Please upgrade your server hardware       | My Samsung smart fridge can handle more entities |

> Reducing mob caps by up to 50% of the Vanilla value is unlikely to be noticeable in most cases. If you have trouble deciding on a value, start with 35, then fine-tune it later.

These numbers are for keeping mob density consistent with Vanilla. As for other categories, there will never be an ideal number since entities like sheep, cows, and fish have more complicated spawning rules. Generate a spark report, analyze it, and make proper adjustments.

#### Entity Categories

Every entity falls under 1 of 7 categories:

| Category                      | bukkit.yml name        | paper-world name              | Contents                                                                                                  |
|-------------------------------|------------------------|-------------------------------|-----------------------------------------------------------------------------------------------------------|
| **monster**                   | `monsters`             | `monster`                     | Warden, Evoker, Wither, Hoglin, Cave Spider, Camel, Husk, Zoglin, Slime, Bogged, Zombified Piglin, Pillager, Wither Skeleton, Zombie, Nautilus, Stray, Blaze, Witch, Piglin Brute, Spider, Drowned, Phantom, Illusioner, Ravager, Vindicator, Creeper, Parched, Elder Guardian, Giant, Breeze, Zombie Horse, Zombie Villager, Endermite, Silverfish, Shulker, Ghast, Vex, Piglin, Guardian, Enderman, Magma Cube, Ender Dragon, Skeleton, Creaking |
| **animals / creature**        | `animals`              | `creature`                    | Wolf, Bee, Horse, Chicken, Frog, Allay, Pig, Skeleton Horse, Llama, Polar Bear, Mule, Armadillo, Donkey, Parrot, Rabbit, Fox, Happy Ghast, Goat, Mooshroom, Cow, Strider, Cat, Sniffer, Ocelot, Trader Llama, Tadpole, Wandering Trader, Panda, Turtle, Camel, Sheep |
| **ambient**                   | `ambient`              | `ambient`                     | Bat (useless — safe to set to zero for no-compromise performance saving)                                   |
| **water-animals / water_creature** | `water-animals`   | `water_creature`              | Nautilus, Dolphin, Squid                                                                                   |
| **water-ambient**             | `water-ambient`        | `water_ambient`               | Cod, Pufferfish, Salmon, Tropical fish                                                                     |
| **water-underground-creature** | `water-underground-creature` | `underground_water_creature` | Glow Squid                                                                                               |
| **axolotl**                   | `axolotls`             | `axolotls`                    | Axolotl                                                                                                   |
| **Misc**                      | —                      | —                             | Projectiles, items, boats, minecarts, villagers, iron golems, etc.                                        |

> **Bat** is the only entity in ambient and has no gameplay functionality — safe to set ambient to 0 for no-compromise performance saving.

#### Villager Optimization

Villagers are complex entities and very resource intensive. They are NOT limited by `spawn-limits` in bukkit.yml. Approaches:

1. **VillagerLobotimizer Plugin** — dynamically remove AI from villagers used as trading hall vendors. Good middle ground for functionality + performance.
2. **Reduce villager tick-rates** — increase `secondarypoisensor` and `validatenearbypoi` values in `paper-world-defaults.yml/tick-rates`.
3. **FarmControl plugin** — introduce a hard cap and communicate the limit to players.
4. **Alternative loot sources** — community trading hall, global admin shop, or customize [WanderingTrades](https://modrinth.com/plugin/wanderingtrades) loot table with superior items.

> The most effective way to optimize villagers is to reduce their number or provide alternative methods for obtaining resources normally supplied by villager trading halls.

### ticks-per

```yaml
ticks-per:
  animal-spawns: 400
  monster-spawns: 1
  water-spawns: 1
  water-ambient-spawns: 1
  water-underground-creature-spawns: 1
  axolotl-spawns: 1
  ambient-spawns: 1
  autosave: 6000
```

Determines the frequency (in ticks) of each entity category making an attempt to spawn. Minecraft will always attempt to spawn entities until it hits the `spawn-limits`. **Establish a proper entity cap on spawn-limits first** — altering ticks-per should be your secondary choice.

**Not Meeting Mobcaps:** If your mob cap cannot be reached in a timely manner, spawn-limits are probably set too high. Use `/paper mobcaps` and `/paper playermobcaps` to monitor. If you see unusually high ticks spent on mob spawning in spark:

```
net.minecraft.server.level.ServerChunkCache.tick() 69.03%
  net.minecraft.server.level.ServerChunkCache.tickChunks() 42.04%
    net.minecraft.server.level.Server.world.level.NaturalSpawner.spawnForChunk() 37.08%
```

This indicates spawn-limits are too high — reduce the mob cap to allow it to be reached more efficiently.

> It is recommended to set tick rates on a per-world basis to address issues specific to particular worlds, utilizing Paper's per-world options.

### Per-World ticks-per-spawn (paper-world-defaults.yml)

```yaml
entities:
  spawning:
    ticks-per-spawn:
      ambient: -1
      axolotls: -1
      creature: -1
      monster: -1
      underground_water_creature: -1
      water_ambient: -1
      water_creature: -1
```

These settings can be individually defined in `[world folder]/paper-world.yml` to override defaults per world.

---

## spigot.yml

### view-distance override

```yaml
view-distance: default
simulation-distance: default
```

This serves as an overwrite to `server.properties`. Putting a value here will overwrite `server.properties`. The value `default` instructs the server to use the value from `server.properties`. Can be set per-world.

### mob-spawn-range

```yaml
mob-spawn-range: 8
```

Radius in chunks around a player in which the server attempts to spawn mobs. Can be altered to adjust perceived mob density.

**Rules:**
- Should always be set to a maximum of `(Simulation Distance - 1)` with a minimum of **3**
- If running Vanilla default simulation-distance of 10, you can adjust between 8–3 without following the above rule
- If mob-spawn-range is higher than simulation-distance, perceived mob density would be lower (monsters attempt to spawn outside simulation-distance)
- Example: simulation-distance of 6 → mob spawn range can be set between 3–5
- Technically 3 is not the minimum, but no mobs will spawn within 24 blocks around the player, so going below 3 drastically reduces the spawnable area

### nerf-spawner-mobs

```yaml
nerf-spawner-mobs: false
```

Removes AI from mobs spawned from a spawner. If your server allows players to relocate spawners, setting this to `true` can reduce lag.

Also toggle `spawner-nerfed-mobs-should-jump` to `true` in `paper-world-defaults.yml` if you enable this — allows mobs to jump so certain farms remain functional.

> See [Things to Avoid](#things-to-avoid) section for why allowing players to silktouch spawners is a bad idea.

### entity-tracking-range

```yaml
entity-tracking-range:
  players: 128
  animals: 96
  monsters: 96
  misc: 96
  display: 128
  other: 64
```

Determines how far away (in **blocks**) an entity is tracked and sent to the client so players can see them.

**Performance diagnostics:** Look in spark report under **Chunk provider tick**:
- `tracker stage 1` — tracking entities
- `tracker stage 2` — broadcast entity tracking changes

If Chunk provider tick is taking significant resources:
1. First try to reduce overall entity counts
2. Then lower simulation distance
3. Reduce tracking range as a **last resort**

**Categories:**
| Category   | Entities                                          |
|------------|---------------------------------------------------|
| `player`   | Players                                            |
| `monster`  | Monster, raider, flying monster                    |
| `animal`   | Villager, water-animal, animal                     |
| `misc`     | Itemframe, painting, sign, dropped item, XP orb     |
| `display`  | Display entity                                     |
| `other`    | Everything not listed above (e.g. armor stand)     |

**Value rules:**
- Maximum of `(simulation-distance - 1) × 16` blocks
- Minimum of `1`
- For small servers with sufficient hardware, can safely increase values to enhance gameplay experience (with performance tradeoff)

> If you make changes to `entity-tracking-range`, please also adjust and match the corresponding category on `entity-activation-range` so players do not see frozen entities.

If experiencing invisible Ghast Ambush, it may be a symptom of `entity-tracking-range` for `monster` being too low. Also check client side `Options > Video Settings > Entity Distance`.

### entity-activation-range

```yaml
entity-activation-range:
  animals: 96
  monsters: 96
  raiders: 96
  misc: 16
  water: 16
  villagers: 32
  flying-monsters: 32
  wake-up-inactive:
    animals-max-per-tick: 4
    animals-every: 1200
    animals-for: 100
    monsters-max-per-tick: 8
    monsters-every: 400
    monsters-for: 100
    villagers-max-per-tick: 4
    villagers-every: 600
    villagers-for: 100
    flying-monsters-max-per-tick: 8
    flying-monsters-every: 200
    flying-monsters-for: 100
  villagers-work-immunity-after: 100
  villagers-work-immunity-for: 20
  villagers-active-for-panic: true
  tick-inactive-villagers: true
  ignore-spectators: false
```

Determines how far away (in **blocks**) an entity should be activated. Any entity outside this zone will be ticked at reduced frequency.

**Value rules:**
- Maximum of `(simulation-distance - 1) × 16` blocks
- Minimum of `16` if running extremely low simulation-distance/view-distance
- Values shown are higher than Paper defaults with default simulation distance of 10 — Vanilla parity should take precedence over potential performance gains
- Set to `0` to disable EAR (Entity Activation Range) entirely — acceptable for most small-to-mid-sized servers

> Keeping the overall entity count under control is a more effective way to avoid performance issues than running a large number of entities with partially broken Vanilla mechanics. **Reducing entity activation range should be the last resort.**

**`tick-inactive-villagers`** can be changed to `false` to only tick villagers within activation range.
- Downside: reduces yield of Iron Golem farms if no player is close by
- Downside: villager trade cooldown timer will not go down if no player is close by

#### wake-up-inactive Explained

Work immunity and wake-up-inactive are implemented by Paper to bring more liveness to the world by allowing entities to "wake up" and do some work for a set amount of time (allows villagers to restock, find work, etc.).

Change `max-per-tick` to `0` if you do not want this behavior for that category.

Example interpretation:

```yaml
wake-up-inactive:
  villagers-max-per-tick: 4
  villagers-every: 600
  villagers-for: 100
villagers-work-immunity-after: 120
villagers-work-immunity-for: 20
```

This means: For every `600` game ticks, there is a chance of up to `4` randomly selected loaded villagers, that has not been active for `120` ticks, to wake up for `100` ticks where they can do stuff for `20` ticks while immune from the freezing effect of being too far away from players.

To disable work immunity, set `villagers-work-immunity-after` to `0` — note this will break villager behavior unless EAR is disabled altogether.

### merge-radius

```yaml
merge-radius:
  item: -1
  exp: -1
```

Paper by default follows the same merge mechanism as Vanilla Minecraft in 1.21. As of Paper 1.21 build #38, the merge behavior has been restored to matching Vanilla Minecraft (`-1` means default).

If you do decide to use the Craftbukkit/Spigot merge feature, the value is in blocks. You can also manually define a value in `paper-world-defaults.yml/entities.behavior.experience-merge-max-value` to merge exp orbs but with a max value per orb.

> It is beneficial to keep the Vanilla mechanic intact, as changing the value here will result in the breakage of farms that rely on XP flows or item merging.

---

## Paper World Defaults

Config location: `config/paper-world-defaults.yml`
Per-world override: `/[world_name]/paper-world.yml`

### tracking-range-y

```yaml
tracking-range-y:
  enabled: true
  animal: default
  display: default
  misc: default
  monster: default
  other: default
  player: default
```

Paper provides the ability to configure vertical `Y level` tracking distances in addition to `entity-tracking-range` in spigot.yml. Especially useful for servers that want entities to appear/disappear earlier or later. Can be enabled per category per world.

### despawn-ranges

```yaml
despawn-ranges:
  ambient:
    hard: default
    soft: default
  axolotls:
    hard: default
    soft: default
  creature:
    hard: default
    soft: default
  misc:
    hard: default
    soft: default
  monster:
    hard:
      horizontal: default
      vertical: default
    soft: default
  underground_water_creature:
    hard: default
    soft: default
  water_ambient:
    hard: default
    soft: default
  water_creature:
    hard: default
    soft: default
```

Defines how far away a mob should have a chance to despawn (`soft`) or instantly despawn (`hard`).

**`default`** means it follows Vanilla Minecraft: soft despawn range = 32, hard despawn range = 128.

Paper offers the ability to separately define the despawn range both **vertically and horizontally**. This is extremely helpful for servers that need to run with a simulation distance lower than the default 10.

#### Rules for Low Simulation Distance

**If simulation-distance is below 10:**
- `mob-spawn-range` should be set to either equal to or less than 8, or to `(simulation-distance - 1)`, whichever value is lower
- `despawn-ranges.hard.horizontal` should be set to `(simulation-distance - 1) × 16`

This ensures that all entities have a chance to despawn before hitting the bordering chunk, preserving natural mob density and preventing unnecessary mob spawning/despawning attempts.

**The vertical value** should always be kept at `default` (128 in Vanilla). This is important to preserve gameplay consistency, as the majority of YouTube farm tutorials instruct players to build their AFK spots accordingly.

> No mobs will naturally spawn within 24 blocks or less around a player so it is not recommended to change hard.horizontal to lower than 36.

> Farm size is still directly limited by simulation distance horizontally. Having the vertical despawn range set to default (128) simply means that players can still build their AFK spot matching Vanilla Minecraft.

#### Despawn Ranges Table for Low Simulation Distance

| simulation-distance | mob-spawn-range | despawn-range.hard.horizontal |
|---------------------|-----------------|--------------------------------|
| 10 (Vanilla)        | 8 (Vanilla)     | 128 (Vanilla)                  |
| 9                   | 8               | 128                            |
| 8                   | 7               | 112                            |
| 7                   | 6               | 96                             |
| 6                   | 5               | 80                             |
| 5                   | 4               | 64                             |
| 4                   | 3               | 48                             |
| 3 (not ideal)       | 3               | 36 (not recommended)           |

To individually define horizontal and vertical despawn ranges:

```yaml
despawn-ranges:
  monster:
    hard:
      horizontal: default
      vertical: default
    soft: default
```

### despawn-time

Paper provides the ability to set despawn times individually for each entity type, in addition to the existing Vanilla despawn rules.

```yaml
despawn-time:
  llama_spit: 1200
  snowball: 1200
  fireball: 1200
  dragon_fireball: 1200
  small_fireball: 1200
  arrow: 3000
  shulker_bullet: 3000
  wither_skull: 3000
  trident: 3000
```

Using `despawn-time` together with `entity-per-chunk-save-limit` and `alt-item-despawn-rate` helps prevent player- or game-generated entities that can sometimes cause performance issues or server crashes.

Complete entity type list: https://minecraft.wiki/w/Java_Edition_data_values#Entities

### entity-per-chunk-save-limit

```yaml
entity-per-chunk-save-limit:
  experience_orb: 50
  snowball: 20
  ender_pearl: 20
  arrow: 20
  fireball: 10
  small_fireball: 10
  dragon_fireball: 5
  egg: 20
  area_effect_cloud: 10
  llama_spit: 5
  shulker_bullet: 8
  splash_potion: 10
  spectral_arrow: 5
  experience_bottle: 5
  trident: 10
  wither_skull: 10
```

Limits the maximum amount of each specified entity saved in a chunk. Essential as it prevents the server from stalling when loading a chunk containing a large number of projectile entities. (Sometimes projectiles are fired into unloaded chunks intentionally by players to crash a server.)

### alt-item-despawn-rate

```yaml
alt-item-despawn-rate:
  enabled: true
  items:
    cobblestone: 600
    cobbled_deepslate: 600
    netherrack: 600
    rotten_flesh: 900
    ender_pearl: 900
    leather: 900
    bone: 1200
    bone_meal: 1200
    cactus: 900
    egg: 900
    feather: 900
    gunpowder: 1200
    arrow: 900
    blaze_rod: 1200
    cod: 1200
    salmon: 1200
    string: 1200
    ink_sac: 900
    slime_ball: 1200
    phantom_membrane: 900
```

Enabling this allows you to despawn commonly dropped items/junk items faster. Value is in **ticks** (20 ticks = 1 second).

- `cactus` added to reduce impact of common cactus farms where items are left on the surface
- `egg` listed to prevent zombies from picking them up and thus preventing despawning

When adding additional items, ensure the value isn't set too low for farms that utilize minecarts in a closed loop to pick up drops.

Note: There is also `item-despawn-rate` in `spigot.yml` that controls all dropped-item despawn timer, but that's a very intrusive change that breaks the 5-minute despawn time promise most players are familiar with.

> The goal of optimizing the server is to make the game more enjoyable for your players, not to make them suffer!

### per-player-mob-spawns

```yaml
per-player-mob-spawns: true
```

Ensures Paper attempts to spawn mobs more evenly across all players online. When enabled, the **global mob cap will scale based on the number of players online.**

**Vanilla mob spawning in multiplayer is inherently flawed:**
- Spawn attempts are made on all loaded chunks around all players
- A vast majority of successful spawn attempts end up around the player with the most favorable spawning conditions
- Example: Two players in the Nether — Player A AFKing on a Nether ceiling Piglin farm while Player B is on Nether Waste biome. Player B gets most mobs simply because there are more spawnable chunks around them overall.

### prevent-moving-into-unloaded-chunks

```yaml
prevent-moving-into-unloaded-chunks: true
```

Prevents players from moving into an unloaded chunk which would otherwise cause a sync-chunk load. When a player moves into an unloaded chunk, the server loads it with the highest priority, thus tanking the TPS.

### redstone-implementation

```yaml
redstone-implementation: ALTERNATE_CURRENT
```

Available options: `VANILLA`, `EIGENCRAFT`, `ALTERNATE_CURRENT` (default is `VANILLA`).

**ALTERNATE_CURRENT** is more efficient and recommended, but comes with possible behavioral changes. Use with caution!

Technical details: https://github.com/SpaceWalkerRS/alternate-current/blob/main/README.md

### tick-rates

```yaml
tick-rates:
  behavior:
    villager:
      validatenearbypoi: -1
  container-update: 1
  dry-farmland: 1
  grass-spread: 1
  mob-spawner: 1
  sensor:
    villager:
      secondarypoisensor: 40
```

Paper provides finer control governing certain ticking rates. Increasing the value reduces resource usage with some cost to respective behaviors.

- `dry-farmland`, `grass-spread`, and `mob-spawner` can be adjusted to increase the interval between each check
- For villager performance issues, try increasing `secondarypoisensor` to `240` and `validatenearbypoi` to `120` — the negative behavioral change is likely not noticeable

### max-entity-collisions

```yaml
max-entity-collisions: 8
```

Maximum amount of entities included in collision lookups. Server stops processing additional entity collisions after this threshold. Lowering helps when animal AI path-finding goes haywire in confined spaces.

**Do not set below `3`** as it will have game-breaking effects on things that rely on collisions.

Not to be confused with `gamerule maxEntityCramming` (default 24) which sets maximum entities that can be crammed together before suffocation damage.

### armor-stands

```yaml
armor-stands:
  do-collision-entity-lookups: true
  tick: true
```

Setting these to `false` will:
- Completely remove any armor stand related lag machines
- Break plugins that utilize armor stands
- Break farms such as automatic ice makers

### optimize-explosions

```yaml
optimize-explosions: false
```

Setting to `true` reduces the impact of calculating large amounts of explosions. If you do enable this and TNT detonation doesn't behave like vanilla, increase `max-tnt-per-tick` threshold in `spigot.yml`. Note that increasing that threshold increases risk of server crashing from large TNT detonation.

### treasure-maps

```yaml
treasure-maps:
  enabled: true
  find-already-discovered:
    loot-tables: default
    villager-trade: true
```

Treasure maps are resource intensive because Vanilla Minecraft searches up to ~1100 block radius for buried treasures.

**Mitigation methods:**
1. **[OkTreasures](https://hangar.papermc.io/Kyle/OkTreasures)** plugin — replaces Vanilla search with custom faster async one
2. **[TreasureMapsPlus](https://hangar.papermc.io/Machine_Maker/TreasureMapsPlus)** — rewards player with chest loottable instead of leading to undiscovered treasure
3. Toggle `villager-trade` under `find-already-discovered` to `true` — reduces performance impact
4. Set `enabled` to `false` to completely disable treasure maps

### spawnChunkRadius (Removed)

As of 1.21.9, the concept of the spawn chunk has been completely removed from the game. The old `paper-world-defaults.yml/spawn.keep-spawn-loaded` config and the later gamerule replacement have both been removed. Use common chunk loaders if you still need that functionality.

### max-auto-save-chunks-per-tick

```yaml
chunks:
  auto-save-interval: default
  max-auto-save-chunks-per-tick: 24
```

**Advanced users only.** The basic formula:

```
max-auto-save-chunks-per-tick × auto-save-interval ≥ total loaded chunks that require save
```

Default works for most servers. If chunk saving is causing performance issues, generate a spark report and consult Paper Discord before changing.

### delay-chunk-unloads-by

```yaml
chunks:
  delay-chunk-unloads-by: 10s
```

Lowering this too low would result in additional work reloading chunks that were just unloaded if a player happens to be near. Default is most likely optimal.

### legacy-ender-pearl-behavior

```yaml
legacy-ender-pearl-behavior: false
```

Since version 1.21.3, Mojang made ender pearls able to load chunks on their own. Setting to `true` disables this ability.

### Additional Merge Optimizations

```yaml
# config/paper-global.yml
misc:
  xp-orb-groups-per-area: default
```

Set a value higher than the default (40) to more aggressively merge experience orbs, reducing performance impact of large/fast XP farms at the cost of some behavior changes.

```yaml
# config/paper-world-defaults.yml
entities:
  behavior:
    only-merge-items-horizontally: true
```

Toggling this further aligns exp orb behavior with Vanilla. Has a slight performance hit but benefits gameplay experience.

---

## Paper Global Settings

Config location: `config/paper-global.yml`

### chunk-loading-advanced

```yaml
chunk-loading-advanced:
  auto-config-send-distance: true
  player-max-concurrent-chunk-generates: 0
  player-max-concurrent-chunk-loads: 0
chunk-loading-basic:
  player-max-chunk-generate-rate: -1.0
  player-max-chunk-load-rate: 100.0
  player-max-chunk-send-rate: 75.0
```

Paper provides control over how chunk data is sent to players. Default values should work for the majority of servers. Do not alter these without fully understanding what they do.

In 1.20+, the `chunk-loading` options have been revised and old global limit configs removed. Defaults work for most servers.

#### Troubleshooting Slow Chunk Loading

1. **Is the map pregenerated?** — Ensure the map is pregenerated to ease server strain
2. **Is the server overloaded?** — Chunk generation is heavy; Paper generates asynchronously
3. **Is Paper anti-xray enabled?** — Anti-xray makes chunks less compressible, increasing network usage
4. **Potential plugin issue?** — Use [Binary Search](https://docs.papermc.io/paper/basic-troubleshooting#binary-search) to isolate problematic plugins
5. **Saturated Netty pipeline?** — Generate spark report with `--thread *`, consider increasing Netty thread count in spigot.yml
6. **Possible network bottlenecks?** — Monitor bandwidth
7. **Possible disk I/O bottleneck?** — Older hardware or shared host limits
8. **Players traveling at high speeds?** — Consider [TooManyGen](https://modrinth.com/plugin/toomanygen) plugin

#### High Ping / Timeout Troubleshooting

1. **Overwhelmed Client** — Paper sends chunks faster than Vanilla; advise players to reduce client view distance or use [client optimizations](https://paper-chan.moe/minecraft-client-optimization/)
2. **Bad Routing / Unstable Internet** — Suggest players install [CloudFlare WARP](https://one.one.one.one/)
3. **Possibly Caused by Plugins** — Use [binary search](https://docs.papermc.io/paper/basic-troubleshooting#binary-search) method

### chunk-system

```yaml
chunk-system:
  gen-parallelism: default
  io-threads: -1
  worker-threads: -1
```

Default values are likely the most optimal for the majority of servers. Strongly advised NOT to manually change these values.

### book (item-validation)

```yaml
book:
  author: 8192
  page: 16384
  title: 8192
book-size:
  page-max: 2560
  total-multiplier: 0.98
display-name: 8192
lore-line: 8192
resolve-selectors-in-books: false
```

Prevents bookban exploits. `page-max` is in bytes — safe to reduce by half or more (e.g. 640–1280). Consider [PacketBooks](https://modrinth.com/plugin/packetbooks) plugin for a more robust solution.

### max-joins-per-tick

```yaml
misc:
  max-joins-per-tick: -1
```

Controls how many players can join per tick. Default (-1) follows Vanilla behavior.

### packet-limiter

```yaml
packet-limiter:
  kick-message: §cPacket limit reached. Sorry, but you are sending too many packets!
  limits:
    all:
      action: DROP
      interval: 5.0
      packet-limit: 3000.0
    serverbound-place:
      action: DROP
      interval: 5.0
      packet-limit: 25.0
```

Paper provides packet rate limiting to prevent abuse and server overload from excessive packet sending.

---

## Per-World Config

All default configs are stored inside `config/` folder. Per-world configs can be defined in `paper-world.yml` located in `/[world_name]/paper-world.yml` (starts empty by default).

Paper allows you to enforce a custom set of configs in `paper-world.yml` to overwrite defaults in `paper-world-defaults.yml`.

### Example Per-World Configs

```yaml
# /world_the_end/paper-world.yml
entities:
  spawning:
    spawn-limits:
      monster: 35
      creature: 10
      ambient: 0
      axolotls: 0
      underground_water_creature: 0
      water_creature: 0
      water_ambient: 0

# /world_nether/paper-world.yml
entities:
  spawning:
    spawn-limits:
      monster: 80
      creature: -1
      ambient: -1
      axolotls: -1
      underground_water_creature: -1
      water_creature: -1
      water_ambient: -1

# /resource_world/paper-world.yml
entities:
  spawning:
    spawn-limits:
      monster: 5
      creature: 30
      ambient: -1
      axolotls: 10
      underground_water_creature: -1
      water_creature: -1
      water_ambient: -1
```

**Name mapping:**
- `creature` = `animals` in bukkit.yml
- `water_creature` = `water-animals` in bukkit.yml

**Value of `-1`** means follow the default value (in case of `spawn-limits`, the mob-cap in bukkit.yml).

**YML formatting:**
- Uses **2 spaces** for indentations (NOT tabs)
- Ensure correct indentation in tree-like structures
- Use a proper YAML editor
- Console will show errors on startup if mistakes are made

> With some clever uses of per-world configs, you can save on server resources while keeping an optimal gameplay experience.

---

## JVM Flags

In Java, JVM flags allow fine tuning of applications, especially around garbage collectors. With modern JVM (Java 21+), the default GC configuration handles Minecraft pretty well. Aikar's flags or ZGC may be beneficial if experiencing GC-related lag spikes, but they are never strictly necessary.

[Start Script Generator](https://docs.papermc.io/misc/tools/start-script-gen) from PaperMC.

### Aikar's Flags (G1GC)

Created by the now-retired PaperMC leadership team member Aikar. Served as the gold standard for fine tuning older Minecraft servers. Set up in a way that is beneficial to the memory behavior of a Minecraft server. Very much recommended for old/outdated Minecraft servers.

Detailed explanation: https://docs.papermc.io/paper/aikars-flags

### Generational ZGC

[ZGC](https://wiki.openjdk.org/spaces/zgc/pages/34668579/Main) is another modern Java garbage collector that may be beneficial for a Minecraft server running Java 21+. No extra flag fine tuning is required.

```bash
-Xms18432M -Xmx18432M -XX:+UseZGC
```

### What NOT to Use

Many have claimed to have cracked the code for the most optimized JVM flags online, but most are either baseless or rely on improper benchmarks. **Avoid blindly copying what others provide.**

- **Setting Xmx equal to Xms** is no longer strictly required with modern JVM. However, having them equal can quickly expose a misconfigured machine or poor hosting practices.
- **Server startup time and idle MSPT** are not useful metrics, nor are they indicators of better GC performance. Many questionable claims use these as benchmark data points — a sign of incompetence.

> The majority of servers will not run into memory issues that require extensive fine tuning. If you are unsure, stick with the conventional options shown above and ask questions in the PaperMC community.

---

## Common Mistakes

### Gigahertz Myth
Do not use clock speed to compare two CPUs unless they are the same model and manufacturer. Select the latest CPU architecture and highest single-core thread rating model available. See [Gigahertz Myth](https://en.wikipedia.org/wiki/Megahertz_myth).

### Allocate More RAM ≠ Better Performance
Server performance is largely dependent on your CPU, not RAM. A majority of servers will be fine with **10GB** allocated regardless of player/plugin count. Any host claiming more RAM increases performance is trying to upsell you.

### RAM Usage ≠ Performance Issues
RAM usage readings from panels/htop are meaningless on a properly set up JVM. Instead, monitor GC intervals and durations for potential issues.

### High Memory Usage ≠ Memory Leak
It may be a symptom but is not necessarily true in most cases. Generate a heap dump during the suspected period with `/paper heap dump` then analyze with Eclipse Memory Analyzer.

### TPS Is Not Accurate
Pay attention to **MSPT** (milliseconds per tick) instead. Minecraft runs at 20 ticks per second, so as long as MSPT is < 50, you maintain 20 TPS. A server showing 20 TPS average but with high percentage of TPS lost may still have players experiencing lag.

### Minimum Thread/Core Count: FOUR
The main game loop runs on 1 thread, but many tasks benefit from multiple threads (Netty, plugins, SQL databases, etc.). At least **4 threads/cores** is recommended. Many budget hosting plans are borderline unusable.

---

## Things to Avoid

### Avoid MobStacker Plugins
Mobstacking is inherently flawed. With mobstacking enabled, the server would never reach mob cap and could be stuck in an endless spawning loop. Combined with zero decently coded stacker plugins, stacking mobs should be avoided at all cost.

### Avoid Lag Removing / Performance Enhancing Plugins
**Fix the root cause of the performance problem instead of masking it.** Paper is already highly optimized. Most performance forks or lag removal plugins further change Vanilla behavior, going against the spirit of optimization. Plugins like ClearLagg or EntityTrackerFixer (ETF) introduce gameplay inconsistencies and can cause permanent damage (ETF removes AI from entities causing permanent brain damage even after removal).

### Do NOT Allow Players to Relocate Spawners
Spawners are basically built-in lag machines when enough are gathered together. For the sake of server performance, do not allow silktouching spawners.

### Do NOT Use Datapacks with Repeat/Recurrent Functions
Datapacks with repeating functions impose a performance hit. Find plugin replacements instead.

### Do NOT Source Plugins from Untrusted Sources
Avoid BlackSpigot, builtbybit, random individuals, or unknown sources. These often contain poorly made resources, backdoors, or stolen code. Obtain plugins only from reputable sites: **GitHub, Hangar, or Modrinth**.

### Do NOT Auto-Update Your Paper.jar
The Paper development cycle does not include proper release/beta versioning, so occasionally a bad build may slip through. Do not blindly download the latest Paper jar for production.

### Do NOT Use Anti-Fabric Plugins
Blocking non-Vanilla clients does NOT reduce cheaters. Most Fabric users want optimization mods. Anti-Fabric plugins only harm legitimate players while cheaters disguise their clients as Vanilla. Using plugins like gProtector or Advanced Security harms your community.

### Anti-cheat Plugin Is NOT a Must
**The best anti-cheat is a mature community.** No singular plugin will catch all cheaters due to how much Minecraft "trusts the client." Focus on community building and active staff audits.

### Avoid Using Plugins to Disable Chat Report
Most concerns around chat reporting have been debunked. Plugins that disable it are often poorly implemented. If you must, use [FreedomChat](https://github.com/e-im/FreedomChat). The chat reporting feature is designed to keep players safe.

### The List of Shame
Avoid everything in [Knenytv's List of Shame](https://kennytv.github.io/list-of-shame) whenever applicable.

---

## Quality of Life Plugins & Tools

### Essential Plugins

| Plugin | Purpose |
|--------|---------|
| [LuckPerms](https://luckperms.net/) | Modern permission plugin with finer control without OP |
| [EssentialsX](https://modrinth.com/plugin/essentialsx) | Essential server features |
| [EssentialsX-Discord](https://essentialsx.net/) | Lightweight MC↔Discord chat bridge |
| [Chunky](https://modrinth.com/plugin/chunky) | World pre-generation |
| [ChunkyBorder](https://modrinth.com/plugin/chunkyborder) | Worldborder with more features |

### Villager / Farm Control

| Plugin | Purpose |
|--------|---------|
| [VillagerLobotimizer](https://modrinth.com/plugin/villagerlobotomy) | Lobotomize villagers in 1×1 rooms, reducing performance impact of trading halls |
| [FarmControl](https://modrinth.com/plugin/farmcontrol) | Solution to overpopulated farms — hard entity caps |
| [MobLimit](https://github.com/Minebench/MobLimit) | Similar to FarmControl (use one or the other) |
| [AntiVillagerLag](https://modrinth.com/plugin/antivillagerlag) | Reduce villager lag without breaking restocking |
| [AntiRaidFarm](https://modrinth.com/plugin/antiraidfarm) | Disable raid farms |

### Performance & Monitoring

| Plugin | Purpose |
|--------|---------|
| [EntityDetection](https://modrinth.com/plugin/entitydetection) | Display entity locations — locate problematic entities and villager clusters |
| [Insights](https://modrinth.com/plugin/insights) | Anti-redstone griefing and block limiter — locate potential lag machines |
| [AntiRedstoneClock-Remastered](https://modrinth.com/plugin/antiredstoneclock-remastered) | Modern anti-redstone clock with staff alerts |
| [TooManyGen](https://modrinth.com/plugin/toomanygen) | Limit players' ability to generate chunks |
| [UnifiedMetrics](https://modrinth.com/plugin/unifiedmetrics) | Feature-rich metrics collection |

### Treasure Map Fixes

| Plugin | Purpose |
|--------|---------|
| [OkTreasures](https://hangar.papermc.io/Kyle/OkTreasures) | Faster async buried treasure search |
| [TreasureMapsPlus](https://hangar.papermc.io/Machine_Maker/TreasureMapsPlus) | Rewards loot directly from map usage |

### Utility & Admin

| Plugin | Purpose |
|--------|---------|
| [PureTickets](https://github.com/broccolai/tickets/releases) | Support ticket system |
| [Vanish No Packet](https://dev.bukkit.org/projects/vanish) | Vanish with style — free and open source |
| [OpenInv](https://github.com/Jikoo/OpenInv) | Open any player inventory, even offline |
| [MiniMOTD](https://modrinth.com/mod/minimotd) | Customize MOTD and server icons |
| [TabTPS](https://modrinth.com/mod/tabtps) | TPS bar integration with RGB colors |
| [AnnouncerPlus](https://modrinth.com/plugin/announcer-plus) | Customizable announcer |
| [Maintenance](https://modrinth.com/plugin/maintenance) | Enable/disable maintenance mode |
| [Bolt](https://modrinth.com/plugin/bolt) | Modern protection for blocks and entities |
| [PacketBooks](https://modrinth.com/plugin/packetbooks) | Modern solution for book exploits |

### Gameplay Enhancement

| Plugin | Purpose |
|--------|---------|
| [Adorena](https://hangar.papermc.io/Emily/adorena) | Scale players in PvP/PvE using new scaling feature |
| [WanderingTrades](https://modrinth.com/plugin/wanderingtrades) | Customize wandering trader loot table |
| [Papertweaks](https://github.com/MC-Machinations/VanillaTweaks/releases) | VanillaTweaks datapack as plugin |
| [TreeAssist](https://github.com/slipcor/TreeAssist) | Tree feller / fast leaf decay that doesn't tank the server |
| [beanstalk](https://modrinth.com/plugin/beanstalk) | Temporary flight management |

### World Editing & Mapping

| Plugin | Purpose |
|--------|---------|
| [FastAsyncWorldEdit](https://modrinth.com/plugin/fastasyncworldedit) | Classic world edit |
| [WorldGuard](https://dev.bukkit.org/projects/worldguard) | Classic anti-grief |
| [BlueMap](https://modrinth.com/plugin/bluemap) | 3D map render |
| [squaremap](https://modrinth.com/plugin/squaremap) | Lightweight 2D Vanilla-themed map |
| [FancyHolograms](https://modrinth.com/plugin/fancyholograms) | Modern hologram plugin (display entity) |

### Security & Logging

| Plugin | Purpose |
|--------|---------|
| [AntiBookBan](https://github.com/Bleep0/AntiBookBan/releases) | Disallow non-ASCII characters in books |
| [OreAnnouncer](https://alessiodp.com/oreannouncer) | Notifies on blocks mined (alternative to anti-xray) |
| [LogBlock](https://github.com/LogBlock/LogBlock) | Grief management |
| [InventoryRollbackPlus](https://github.com/TechnicallyCoded/Inventory-Rollback-Plus) | Restore player inventory from death |
| [CoreProtect](https://github.com/PlayPro/CoreProtect/) | Block logging/rollback (use preview feature for x-ray audits) |

### Proxy & Other

| Plugin | Purpose |
|--------|---------|
| [ViaVersion](https://github.com/ViaVersion/ViaVersion/releases) | Allow newer Minecraft client versions to join |
| [Vault](https://github.com/MilkBowl/Vault/releases) | Abstraction library |
| [ChestShop](https://modrinth.com/plugin/chestshop) | Simple chest shop |
| [DecentHolograms](https://github.com/DecentSoftware-eu/DecentHolograms/releases) | Hologram plugin without performance holes |

---

## Anti-Xray Reference

Paper has an efficient built-in anti-xray: [PaperMC Anti-Xray Documentation](https://docs.papermc.io/paper/anti-xray)

- `engine mode 1` — basic protection, leaves ores exposed to air untouched
- `engine mode 2 & 3` — obscures views by presenting fake ores to client
- On servers with 100+ concurrent players, `engine mode 2` may saturate network pipelines

**Alternative methods:**
1. [RayTraceAntiXray](https://github.com/stonar96/RayTraceAntiXray) — unpassable solution with additional CPU usage
2. Manual staff audit combining [OreAnnouncer](https://alessiodp.com/oreannouncer) + [CoreProtect](https://github.com/PlayPro/CoreProtect/) preview feature — 100% effective, zero additional resources

**How to Manual Audit:**
1. Be notified by OreAnnouncer about unusual ore amounts
2. Teleport to mining coordinates
3. Run `/co rollback action:-block exclude:stone,deepslate,dirt,gravel,andesite,diorite,granite radius:8 time:24h #preview`
4. If player is digging toward ores without line of sight → strong indication of x-ray

---

## Feature Seeds (Anti Seed-Cracking)

```yaml
generate-random-seeds-for-all: true
```

Randomizes sub-seeds rather than using world seed for features. Provides security against [SeedcrackerX](https://github.com/19MisterX98/SeedCrackerX).

**Setup for new world:**
1. Start server, then stop it
2. Set `generate-random-seeds-for-all` to `true` in `paper-world-defaults.yml`
3. Manually input structure seeds in `spigot.yml`
4. Remove `world`, `world_nether`, `world_the_end` folders
5. Optionally define individual feature-seeds in `paper-world-defaults.yml`
6. Start server

Do NOT enable on existing worlds — may produce cutoff structures, misaligned terrain, and break `/locate`.

---

## Lootables (Auto-Replenish)

```yaml
lootables:
  auto-replenish: false
  max-refills: -1
  refresh-max: 2d
  refresh-min: 12h
  reset-seed-on-fill: true
  restrict-player-reloot: true
  restrict-player-reloot-time: disabled
```

Toggle `auto-replenish` to `true` for long-term survival servers. Time units: `s` seconds, `m` minutes, `h` hours, `d` days. **`m` is NOT months!**

---

## Performance Ceiling

At the time of writing, even with the latest hardware:
- **60–80 players** with close to vanilla default configs
- **100 players** with huge gameplay compromises

...is the hard ceiling. At that point, impose a reasonable max player limit and start thinking about network expansions with multiple servers.

---

## Backup & Recovery

Having a backup and recovery plan is essential. Unexpected crashes or improper shutdowns can cause world corruption or data loss.

**Backup solutions with snapshot features:**
- [BorgBase](https://www.borgbase.com/)
- [borgmatic](https://torsion.org/borgmatic)
- [Kopia](https://kopia.io/) (supports Windows)
- [rsync.net](https://rsync.net/)
- [Hetzner storage box](https://www.hetzner.com/storage/storage-box)
- [restic](https://restic.net/)

**Basic backup:**
- Linux: `tar -czvf backup_date.tar.gz /[path]/`
- Windows: Right Click folder > Send to > Compressed (zipped) folder

> An untested backup is as good as no backup. Make sure to test them regularly.

---

## Hosting Checklist

- **CPU Model Transparency** — plan should clearly specify CPU model; avoid anything before AMD Ryzen 3900
- **Support for custom JVM flags** (such as Aikar's flags); host should allow Xmx = Xms
- **Public Node Status** — publicly accessible node status showing resource usage in real time
- **Anti-DDoS protection**
- **Offsite backup option** — must-have; any host without this is an automatic pass
- **Well-defined SLA and properly registered business**
- **Customer support** with good track record

---

## Helpful Links

- GitHub: https://github.com/PaperMC
- Discord: https://discord.gg/PaperMC
- Forum: https://forums.papermc.io
- Wiki: https://docs.papermc.io
- JavaDocs: https://jd.papermc.io
- Paper Chan Discord: https://paper-chan.moe/discord