# Server Configuration Review Guide

Comprehensive guide for reviewing Minecraft server configurations based on spark profile data, with gamemode-specific recommendations, bug-config warnings, and safety checks.

---

## Overview

This guide is used AFTER spark profile analysis identifies performance issues. It covers:

1. **Gamemode-aware recommendations** - Different server types need different configs
2. **Bug-config warnings** - Configs that improve performance but introduce bugs or gameplay issues
3. **Safety rules** - Settings that should NEVER be changed or changed only with extreme caution
4. **Review checklist** - Systematic approach to config review

---

## Gamemode Classification

### Determining Server Type from Spark Data

| Signal in Spark Data | Server Type |
|---|---|
| High entity variety, vanilla-like mob spawning, long player sessions | **SMP / Survival** |
| Very low entity count, no mob spawning, high player join/leave rate | **Lobby / Hub** |
| Temporary entity bursts, moderate mob count, frequent entity spawn/despawn | **Minigame (Bedwars, Skywars, etc.)** |
| Redstone-heavy, hopper-heavy, entity farms in stack traces | **SMP with farms** |
| High chunk I/O, frequent world loads/unloads | **Minigame network** |
| Very high player count, spread across world | **Large survival / Folia** |
| Mod-heavy stack traces (non-net.minecraft packages) | **Modded** |

---

## Gamemode-Specific Configuration Profiles

### SMP / Survival (Vanilla-Adjacent)

**Philosophy**: SMP servers depend on vanilla-like mob behavior, farm functionality, and game mechanics. Config changes must preserve gameplay integrity. Performance is gained through smart tuning, not by breaking vanilla mechanics.

#### Safe to Change (Vanilla-Compatible)

| Config | Recommended Range | Notes |
|--------|------------------|-------|
| `view-distance` | 5-8 | Higher = more RAM, more chunk sends. 6-7 is typically optimal. |
| `simulation-distance` | 4-6 | **Critical**: Must not be lower than farm minimum requirements. |
| `entity-activation-range` | 16-32 | Lower values save CPU but mobs appear frozen until close. |
| `entity-tracking-range` | 32-64 | Visual only. Can be lowered without breaking gameplay. |
| `spawn-limits.monsters` | 30-50 | Use spawn-limit/mob-spawn-range cheat sheet to maintain density. |
| `merge-radius.item` | 3.0-4.0 | Safe for gameplay. Items still merge in vanilla-like manner. |
| `merge-radius.exp` | 4.0-6.0 | Safe. XP orbs merge more aggressively. |
| `entity-per-chunk-save-limit` | See reference | Prevents chunk loading exploits. Essential safety config. |
| `alt-item-despawn-rate` | Enable for junk items | Accelerated despawn for cobblestone, netherrack, etc. |
| `mob-spawn-rate.monster` | 2-4 ticks | Slightly fewer spawn attempts. Barely noticeable. |
| `despawn-ranges` | Match simulation-distance | See despawn range table in optimization guide. |
| `tracking-range-y` | Enable, set 16-32 | Vertical tracking limits. Huge savings in tall worlds. |
| `arrow-despawn-rate` | 200-600 | Arrows in ground are ticking entities. Safe to lower. |

#### DO NOT CHANGE (Breaks Vanilla Gameplay)

| Config | Why NOT to Change | Bug/Risk |
|--------|-------------------|---------|
| `simulation-distance < 4` | Farms break. Mobs won't spawn correctly. Mob farms require `(sim-dist - 1) x 16` blocks radius. Below 4, most farms stop working. | **Farms broken**: Iron farms, gold farms, witch farms, ALL mob-based farms fail. |
| `mob-spawn-range < 3` | Spawn area becomes too small. No mobs spawn within 24 blocks of player. Below 3 chunks, there is barely any spawnable area. | **No mobs**: Players report empty caves, no hostile mobs. |
| `hopper-transfer` set to `1` | Hoppers transfer every tick instead of every 8 ticks. This makes hoppers the #1 lag source. | **Server-destroying**: Hopper-based farms run 8x faster, but server TPS tanks. NEVER set to 1. |
| `hopper-transfer` above `8` | Hoppers become too slow. Item sorting and farm timing break. | **Farms broken**: Sorters and timers fail. Keep at 8. |
| `nerf-spawner-mobs: true` | Spawner mobs lose ALL AI. They stand still and don't attack or move. | ** farms broken**: Any farm using mob AI (iron golem farms, etc.) breaks. Only use if you explicitly want spawner mobs to not function. |
| `max-entity-collisions < 3` | Entities stop interacting properly. Minecarts don't link, boats don't work. | **Game-breaking**: Transportation and entity interactions fail below 3. |
| `tick-inactive-villagers: false` | Villagers outside activation range stop restocking trades. Iron golem farms stop producing when no player is nearby. | **Farms broken**: Iron golem farms and villager trading halls break. |
| `despawn-ranges.hard < 36` | Mobs despawn too close to players, destroying mob farm functionality. | **Mobs vanishing**: Hostile mobs randomly disappearing near players. |
| `despawn-ranges.vertical` changed from default | AFK spots in vanilla farm tutorials rely on vertical despawn behavior. Changing this breaks all farm tutorials. | **Farms broken**: Every YouTube farm tutorial assumes default vertical despawn. |

#### Use With Caution (Trade-Offs)

| Config | Trade-Off | Warning |
|--------|-----------|---------|
| `spawn-limits.monsters < 15` | Higher performance, fewer mobs | Players will notice fewer hostile mobs. Use mob-spawn-range adjustment to maintain density feel. |
| `villager activation-range < 16` | Much less villager CPU | Villagers appear frozen until player is very close. Trade halls look lifeless. |
| `villager tick-rates increased` | Less villager CPU | Villagers take longer to restock, pathfind less. May cause complaints. |
| `redstone-implementation: ALTERNATE_CURRENT` | Better redstone performance | **Behavior difference**: Some redstone circuits behave differently. Test all redstone builds on your server before enabling. |
| `prevent-moving-into-unloaded-chunks: true` | Prevents sync chunk loads | **Minor gameplay change**: Elytra players may experience rubber-banding at world borders. Still recommended. |
| `armor-stands.tick: false` | Removes armor stand ticking | **Breaks**: Automatic ice makers, some plugins that use armor stands. |
| `optimize-explosions: true` | Faster explosion calculation | **Behavior difference**: TNT behavior may differ from vanilla. Test before enabling. |
| `merge-radius.item > 5.0` | Fewer item entities | Items merge from far away, which can break farm item collection (items teleport to center). |

---

### Lobby / Hub

**Philosophy**: Lobby servers have NO vanilla gameplay requirements. Players don't farm, fight mobs, or build. Optimization can be aggressive - disable everything that isn't needed for the lobby experience.

#### Aggressive Optimization (All Safe for Lobby)

| Config | Value | Reason |
|--------|-------|--------|
| `view-distance` | 3-4 | Lobby is usually small. No need for distant terrain. |
| `simulation-distance` | 0 (if Paper) or minimum | **No mobs, no farms** = no need for simulation. |
| `spawn-limits.monsters` | 0 | No hostile mobs needed. |
| `spawn-limits.animals` | 0 | No animals needed. |
| `spawn-limits.water-animals` | 0 | No water mobs. |
| `spawn-limits.ambient` | 0 | No bats. |
| `mob-spawn-rate` | -1 (disabled) | No mob spawning at all. |
| `entity-activation-range` | All categories: 0-4 | Nothing needs to be active. |
| `entity-tracking-range` | Minimize | Only track players and needed entities. |
| `merge-radius.item` | 10.0+ | Aggressively merge drops. |
| `merge-radius.exp` | 10.0+ | Aggressively merge XP. |
| `arrow-despawn-rate` | 20 | Arrows disappear almost instantly. |
| `hopper-transfer` | 8 (still default) | Even on lobby, never set to 1. |
| `max-entity-collisions` | 1 | Minimal entity interaction needed on lobby. |
| `nerf-spawner-mobs` | true (if any spawners exist) | No mob AI needed. |
| `allow-nether` | false | No nether needed. |
| `allow-end` in bukkit.yml | false | No end needed. |

#### Gamerule Optimizations for Lobby

| Gamerule | Value | Reason |
|----------|-------|--------|
| `doMobSpawning` | false | No mob spawning needed |
| `doDaylightCycle` | false | Lock time. No day/night cycle processing. |
| `doWeatherCycle` | false | Lock weather. No rain processing. |
| `doFireTick` | false | No fire spread needed. |
| `mobGriefing` | false | No mob block changes needed. |
| `randomTickSpeed` | 0 | No crop/tree growth needed. |
| `doTileDrops` | false or true | Depends on lobby design (false = no item lag) |

#### Lobby-Specific Warning

| Config | Warning |
|--------|---------|
| `simulation-distance = 0` | **BRAKE WARNING**: Entities with custom names won't despawn. Armor stands, NPCs (via Citizens plugin), and named entities still tick. Use `entity-per-chunk-save-limit` for safety. |
| Disabling all gamerules | **BRAKE WARNING**: If your lobby uses fire, water, arrows, or any vanilla mechanics for minigame features, those WILL break. Only disable what your lobby actually doesn't use. |
| `view-distance` too low | If lobby has large builds or parkour, players will see chunks loading. 4 is minimum for most lobbies. |

---

### Bedwars / Skywars / Minigames

**Philosophy**: Minigame servers have specific, well-defined gameplay requirements. The in-game phase has entity bursts, combat, and redstone (traps). The lobby phase is lightweight. Optimize based on the phase.

#### Per-World Config for Minigames

| Config | Arena World | Lobby World | Reason |
|--------|-------------|-------------|--------|
| `simulation-distance` | 4-6 | 0-4 | Arena needs simulation for combat; lobby doesn't. |
| `spawn-limits.monsters` | 0 | 0 | Most minigames don't use natural mob spawning. |
| `spawn-limits.animals` | 0 | 0 | Not needed. |
| `view-distance` | 4-5 | 3-4 | Arena maps are usually small/pre-generated. |
| `entity-activation-range` | Standard | Minimal | Arena entities need to be active; lobby doesn't. |
| `merge-radius.item` | 4.0 | 10.0+ | Arena items need vanilla-like merging; lobby can be aggressive. |
| `arrow-despawn-rate` | 100-200 | 20 | Arena arrows persist longer for gameplay; lobby don't need them. |
| `max-entity-collisions` | 4-8 | 1 | Arena needs entity interactions (bed breaking, projectile hits); lobby doesn't. |

#### Bedwars-Specific

| Config | Value | Reason |
|--------|-------|--------|
| `max-entity-collisions` | >= 4 | **CRITICAL**: Below 4, TNT knockback and entity interactions in Bedwars break. Players can't be pushed by explosions properly. |
| `arrow-despawn-rate` | 100-300 | Arrows used in combat. Too low = arrows vanish mid-fight. |
| `merge-radius.item` | 2.5-3.5 (vanilla-ish) | **CRITICAL**: Bedwars relies on resource items spawning at generators. High merge radius causes items to teleport together, breaking resource timing and visual feedback. |
| `hopper-transfer` | 8 (default) | Never change from 8. |
| `nerf-spawner-mobs` | false (if using resource spawners) | Many Bedwars plugins use spawner-like mechanics that may be affected. |
| `doMobSpawning` gamerule | false | Minigames typically don't need natural spawning. |
| `doTileDrops` gamerule | depends | If blocks drop items on break, keep true. If using custom drops, can disable. |

#### Skywars-Specific

| Config | Value | Reason |
|--------|-------|--------|
| `view-distance` | 4-5 | Islands are pre-generated. No terrain exploration. |
| `simulation-distance` | 4-6 | Combat needs entity ticking. |
| `merge-radius.item` | 3.0-4.0 | Moderate merging. Loot on islands should be pickup-able. |
| `arrow-despawn-rate` | 100-200 | Arrows in combat need to persist. |
| `doFireTick` gamerule | depends | If your Skywars map has fire mechanics, keep true. |

#### Minigame Warning Flags

| Warning | Why It Matters |
|---------|---------------|
| `merge-radius.item` too high | Resources merge mid-air in Bedwars generators. Players see items jumping together. **Breaks game feel.** |
| `max-entity-collisions < 4` | TNT and knockback in Bedwars rely on entity collision. Below 4, explosion knockback doesn't work correctly. |
| `entity-per-chunk-save-limit` too aggressive | TNT entities deleted mid-fight. Set TNT limit to 50+, fireballs to 8+. |
| `doFireTick = false` | If minigame uses fire (bed burning in Bedwars, lava in Skywars), fire won't spread or burn. |
| `randomTickSpeed = 0` | If minigame has crop growth mechanics, crops won't grow. |
| Disabling `doMobSpawning` | Some minigames use silverfish, blazes, or other mobs as game mechanics. |

---

### Factions / Claim-Based PvP

**Philosophy**: PvP servers need responsive combat, entity tracking for players and projectiles, and chunk loading for raids. Optimization must not introduce PvP disadvantages.

#### Factions-Specific Config

| Config | Value | Reason |
|--------|-------|--------|
| `view-distance` | 5-7 | Players need to see raiders. Too low = PvP disadvantage. |
| `simulation-distance` | 4-6 | Combat needs entity ticking. |
| `entity-activation-range.monsters` | 24+ | **Mobs must be active** for PvP (creeper explosions, zombie reinforcements). Lower = unfair advantage. |
| `entity-activation-range.players` | 48+ | Players must be active at distance for combat prediction. |
| `entity-tracking-range.players` | 64-128 | **CRITICAL**: Low tracking = invisible raiders. Must be high. |
| `arrow-despawn-rate` | 300-600 | PvP arrows need to exist for bow combat. |
| `merge-radius.item` | 2.5-3.5 | Keep close to vanilla. Loot needs to be visible and pickup-able. |
| `max-entity-collisions` | 4-8 | PvP knockback needs entity collisions. |
| `network-compression-threshold` | 256-512 | Combat needs responsive packets. |
| `hopper-transfer` | 8 (default) | Never change. |
| `doInsomnia` gamerule | depends on server | If false, phantoms never spawn. Popular on PvP servers. |
| `doMobSpawning` | true | Hostile mobs are part of the survival PvP experience. |

#### Factions Warning Flags

| Warning | Why It Matters |
|---------|---------------|
| Low `entity-tracking-range.players` | Raiders become invisible at distance. **PvP-breaking.** |
| Low `entity-activation-range.monsters` | Creepers don't explode until player is point-blank. Zombies don't fight back. |
| `nerf-spawner-mobs: true` | If factions use spawners for mob defenses, they're nerfed. |
| `arrow-despawn-rate < 100` | Arrows vanish during PvP bow fights. |
| `doFireTick: false` | If factions plugin uses fire spread for raids, it won't work. |

---

### Creative / Building

**Philosophy**: Creative servers have minimal entity load but high chunk load for building. Optimize for chunk sending and player connections, not entity management.

#### Creative-Specific Config

| Config | Value | Reason |
|--------|-------|--------|
| `view-distance` | 7-10 | Builders need to see their creations. Priority setting. |
| `simulation-distance` | 0-4 | No need for mob ticking. 0 if no game mechanics needed. |
| `spawn-limits` (all) | 0 | No mobs needed in creative. |
| `mob-spawn-rate` | -1 | Disable spawning entirely. |
| `entity-activation-range` (all) | 0-4 | No entity AI needed. |
| `merge-radius.item` | 5.0+ | Items should merge aggressively - not important in creative. |
| `max-entity-collisions` | 1 | No entity interaction needed. |
| `doMobSpawning` | false | No mobs. |
| `doDaylightCycle` | false | Lock time. |
| `doWeatherCycle` | false | Lock weather. |
| `randomTickSpeed` | 0 | No growth needed. |

#### Creative Warning Flags

| Warning | Why It Matters |
|---------|---------------|
| `view-distance` too low | Builders can't see their builds. Core creative experience ruined. |
| `simulation-distance: 0` | Some creative plugins use entities (armor stands for decoration). Keep at 4 if using Citizens, armor stand plugins. |

---

### Modded (Fabric/Forge)

**Philosophy**: Modded servers carry heavy baseline load from mods. Less room for optimization because mods add mandatory ticking entities, chunk generation, and processing. Focus on JVM tuning and view distance.

#### Modded-Specific Config

| Config | Value | Reason |
|--------|-------|--------|
| `view-distance` | 4-6 | Mods already add massive load. Keep low. |
| `simulation-distance` | 4 | Even mods need simulation. Don't go lower. |
| `entity-activation-range` | Close to vanilla defaults (24-32) | **Many mods tick their own entities regardless of activation range, but some don't.** |
| `spawn-limits` | Slightly reduced (80% of vanilla) | Mods add their own entities. Lower vanilla spawns slightly. |
| `max-joins-per-tick` | 2-3 | Modded servers load more data on join. Throttle joins. |
| JVM heap | 1.5-2x expected usage | Mods use significantly more memory. |
| GC | ZGC (JDK 21+) or Aikar's G1GC | Modded needs good GC tuning due to high allocation rates. |

#### Modded Warning Flags

| Warning | Why It Matters |
|---------|---------------|
| Low `entity-activation-range` | **Many mods bypass activation range.** Some mods hard-crash if their entities aren't ticked. Research specific mod requirements before changing. |
| Low `spawn-limits` | Mods may add mandatory entities that count toward caps. Reducing vanilla caps too low can prevent mod entities from spawning. |
| Aggressive `merge-radius` | Mod items with NBT data shouldn't merge. High merge radius can cause items to vanish or combine incorrectly. |
| `doMobSpawning: false` | Many mods use natural spawning for their content. Disabling it breaks mod content. |

---

### Skyblock

**Philosophy**: Skyblock servers have concentrated entity load (farms, spawners on small islands) with low total world population per player. Per-player optimization is key.

#### Skyblock-Specific Config

| Config | Value | Reason |
|--------|-------|--------|
| `view-distance` | 4-5 | Islands are small. Players don't explore. |
| `simulation-distance` | 4 | Minimum for farms to function. |
| `spawn-limits.monsters` | 20-35 | Lower because islands concentrate mobs. Per-player-mob-spawns helps. |
| `mob-spawn-range` | 3-4 | Small islands don't need large spawn range. |
| `entity-activation-range` | 16-24/16/8/8/16 | Mobs should activate when player is on their island but not from other islands. |
| `merge-radius.item` | 3.5-4.5 | Farms produce many items. Aggressive merging helps. |
| `merge-radius.exp` | 5.0-6.0 | XP farms produce many orbs. |
| `hopper-transfer` | 8 (NEVER change) | Skyblock depends heavily on hopper automation. |
| `entity-per-chunk-save-limit.item` | 100-200 | Higher than usual because farms produce many drops. |
| `alt-item-despawn-rate` | Enable for common junk | Faster cleanup of cobblestone, etc. |

#### Skyblock Warning Flags

| Warning | Why It Matters |
|---------|---------------|
| `hopper-transfer != 8` | **CRITICAL**: Skyblock REQUIRES hoppers. Setting to 1 tanks TPS. Setting above 8 breaks all farm timing. |
| `simulation-distance < 4` | **Farms break**: Spawners and mob farms need simulation to work. |
| Low `entity-per-chunk-save-limit.item` | Farm items get deleted. Players lose crops/minerals. |
| `tick-inactive-villagers: false` | Trading hall villagers stop restocking when no one is near. Skyblock trading halls are core gameplay. |
| `nerf-spawner-mobs: true` | If using silktouch spawners, spawner mobs won't function. Many skyblock plugins depend on this. |

---

## Bug-Config Warnings

These are configurations that improve raw performance numbers but introduce bugs, gameplay issues, or hidden problems. **Always warn the user before recommending these.**

### Critical Bug-Config Warnings

#### 1. `hopper-transfer: 1` (Spigot tick-rates)

| Aspect | Detail |
|--------|--------|
| **What it does** | Hoppers transfer items every tick instead of every 8 ticks |
| **Why people set it** | Faster item transport in farms |
| **Bug introduced** | Hoppers become the #1 lag source on the server. Every hopper processes 8x more often. A 10-hopper system goes from 80 hopper-ticks/item to 80 hopper-ticks/second. |
| **Secondary bug** | Item sorters and timing-based redstone break because they're calibrated for 8-tick transfer rate |
| **Correct approach** | Keep at 8. Reduce hopper count in builds. Use water streams for transport. |

#### 2. `max-entity-collisions < 3`

| Aspect | Detail |
|--------|--------|
| **What it does** | Limits entity collision processing |
| **Why people set it** | Reduce CPU from entity collision checks |
| **Bug introduced** | Minecarts won't link together. Boats become unusable. Entity stacking and cramming breaks. |
| **Threshold** | Must be >= 3. Below 3 is game-breaking. |
| **Correct approach** | Use 4-8. Never below 3. |

#### 3. Storage Tick Desync (Hopper + Chest Timing)

| Aspect | Detail |
|--------|--------|
| **What it is** | Not a single config, but a class of bugs caused by changing `hopper-transfer`, `hopper-check`, or container tick rates |
| **Bug introduced** | Items duplicate or vanish when hopper timings are modified. Inventory desync between client and server. |
| **Correct approach** | Keep all hopper-related timings at vanilla values. If hopper lag is an issue, reduce the NUMBER of hoppers, not the timing. |

#### 4. `simulation-distance: 0` or `1`

| Aspect | Detail |
|--------|--------|
| **What it does** | Disables or severely limits chunk ticking |
| **Why people set it** | Maximum entity performance |
| **Bug introduced** | No mobs spawn. No crop growth. No redstone. No water flow. No fire spread. Villagers freeze. Iron golem farms stop. |
| **When acceptable** | Only on lobby/hub worlds where no gameplay occurs. |
| **Correct approach** | Use 4 minimum for any world with gameplay. |

#### 5. Excessive `merge-radius` (> 5.0 for items)

| Aspect | Detail |
|--------|--------|
| **What it does** | Items merge from further away |
| **Why people set it** | Reduce item entity count |
| **Bug introduced** | Items "teleport" mid-air toward each other. Harvesting items becomes harder because they clump in center of drop area. Farm item collection breaks (pipes, water streams can't catch items that merged away). |
| **Threshold** | Keep item merge below 4.5, exp merge below 6.0 for SMP. Lobby can go higher. |
| **Correct approach** | Use per-item `alt-item-despawn-rate` instead to remove junk items faster. |

#### 6. `despawn-ranges` Too Low

| Aspect | Detail |
|--------|--------|
| **What it does** | Mobs despawn closer to players |
| **Why people set it** | Reduce mob count and CPU |
| **Bug introduced** | Mobs vanish while the player can still see them. "Mobs popping in and out" is reported as a bug by players. Farm designs break because despawn range determines farm size. |
| **Rule** | `despawn-ranges.hard.horizontal` must be >= `(simulation-distance - 1) x 16` AND >= 36. `despawn-ranges.vertical` should stay at default (128). |

#### 7. `tick-inactive-villagers: false`

| Aspect | Detail |
|--------|--------|
| **What it does** | Villagers outside activation range stop ticking entirely |
| **Why people set it** | Huge villager CPU savings (most impactful villager optimization) |
| **Bug introduced** | Iron golem farms produce nothing when no player is nearby. Villager restock timers freeze. Trading halls appear "frozen" until player walks close. |
| **When acceptable** | On servers where villager trading halls aren't core gameplay (Factions PvP, some minigames). |
| **Correct approach** | For SMP/survival: Use `VillagerLobotimizer` plugin instead, which removes AI from villagers in 1x1 spaces while keeping them functional for trading. |

#### 8. `nerf-spawner-mobs: true`

| Aspect | Detail |
|--------|--------|
| **What it does** | Spawner mobs get no AI - they don't move, attack, or pathfind |
| **Why people set it** | Massive CPU savings from mob spawners |
| **Bug introduced** | Any farm using spawner mob AI breaks (iron golem farms, mob-based defenses). Spawner mobs stand completely still. |
| **When acceptable** | If spawners are purely decorative or your server doesn't use spawners for gameplay. |
| **Correct approach** | Use `spawner-nerfed-mobs-should-jump: true` in paper-world config if you enable this, so some farms still partially work. |

#### 9. Aggressive `entity-per-chunk-save-limit`

| Aspect | Detail |
|--------|--------|
| **What it does** | Limits entity count saved per chunk |
| **Why people set it** | Prevents chunk loading exploits (crashing server by loading chunks full of entities) |
| **Bug introduced** | If set too low, entities that players placed intentionally (minecarts, boats, armor stands) get deleted on chunk reload. |
| **Safe values** | Use the reference table values. Never set `item` below 40, `tnt` below 20 (Bedwars needs 50+), `arrow` below 16. |
| **Correct approach** | Set reasonable limits (see reference table). This is a SAFETY config, not a performance config. |

#### 10. `doDaylightCycle: false` on SMP

| Aspect | Detail |
|--------|--------|
| **What it does** | Time stops advancing |
| **Why people set it** | Saves ~0.1ms/tick (negligible) |
| **Bug introduced** | Crops don't grow correctly (some growth checks need day/night cycle). Mob spawn rates change ( spawns depend on darkness). Sleeping in beds becomes impossible. |
| **When acceptable** | Only on lobby, creative, or minigame worlds. |
| **Correct approach** | Don't use on SMP. The performance gain is negligible. |

---

## Safety Rules (NEVER Change)

These configs should NEVER be modified regardless of gamemode, or should only be changed with explicit user understanding of consequences.

### Absolute Never-Change Rules

| Rule | Why |
|------|-----|
| `hopper-transfer` must stay at `8` | Changing it to 1 creates massive lag. Changing it above 8 breaks all hopper timing. |
| `hopper-amount` must stay at `1` | Changing it alters item economy and breaks hopper systems. |
| `max-entity-collisions` must be >= `3` | Below 3 breaks minecarts, boats, and entity interactions. |
| `simulation-distance` must be >= `4` for gameplay worlds | Below 4 breaks mob spawning, farms, and vanilla mechanics. |
| `mob-spawn-range` must be <= `simulation-distance - 1` | Mobs spawning outside simulation distance wastes spawn cycles. |
| `mob-spawn-range` must be >= `3` | Below 3, the spawnable area is too small for any mobs to spawn. |

### Conditional Never-Change (Gamemode-Dependent)

| Rule | Applies To | Why |
|------|-----------|-----|
| Don't disable `doMobSpawning` | SMP, Factions, Skyblock | Hostile mobs are core gameplay. |
| Don't set `merge-radius.item > 5.0` | Bedwars, Skyblock, SMP | Item collection in farms and generators breaks. |
| Don't lower `entity-tracking-range.players < 48` | PvP, Factions | Players become invisible to each other. |
| Don't lower `arrow-despawn-rate < 100` | PvP, Factions, Minigames | Arrows vanish during bow combat. |
| Don't set `despawn-ranges.hard.horizontal < 36` | SMP, Skyblock | Mobs vanish visibly near players. |

---

## Config Review Workflow

### Step 1: Identify Server Type

From spark profile `info` command, determine:
1. Platform (Paper/Spigot/Folia/Canvas)
2. Minecraft version
3. Plugin list (identifies gamemode plugins like Bedwars, Skyblock, etc.)
4. Player count patterns

### Step 2: Get Current Configuration

Ask the user for their current config files:
- `server.properties`
- `spigot.yml`
- `paper-global.yml` (if Paper)
- `paper-world.yml` or `paper-world-defaults.yml` (if Paper)
- `bukkit.yml`
- Startup script (for JVM flags)

Or extract from spark data where possible.

### Step 3: Systematic Review

Review each config against the gamemode profile. For each setting:

1. **Is the current value safe?** (Doesn't break gameplay for the server type)
2. **Is the current value optimal?** (Good balance of performance and experience)
3. **Are there any bug-config risks?** (Performance gains that come with hidden costs)
4. **Are there any dependency issues?** (Values that must be changed together, like spawn-limits + mob-spawn-range)

### Step 4: Generate Recommendations

Format recommendations as:

```
RECOMMENDED CHANGE: [config] = [value] (currently: [current_value])
  Reason: [why]
  Risk: [none/low/medium/high]
  Gamemode impact: [how it affects gameplay]

WARNING: [config] = [current_value] - [issue]
  This can cause: [specific bug]
  Consider: [alternative]
```

### Step 5: Validate Recommendations

Before presenting to the user, verify:

1. **No NEVER-change rules are violated** by any recommendation
2. **Gamemode constraints are respected** (SMP = preserve vanilla, Lobby = aggressive OK)
3. **Related configs are consistent**:
   - `mob-spawn-range <= simulation-distance - 1`
   - `entity-activation-range <= (simulation-distance - 1) x 16`
   - `entity-tracking-range >= entity-activation-range` (visual should be >= activation)
   - `spawn-limits` and `mob-spawn-range` follow the density cheat sheet
   - `view-distance >= simulation-distance`
4. **JVM flags are correct** for the heap size and JDK version
5. **Per-world configs are consistent** with each other

### Step 6: Present with Warnings

Always include:
- A summary table of all recommended changes
- Risk level for each change (safe/low-risk/needs-testing)
- A "DO NOT CHANGE" list if current values are already at dangerous levels
- Gamemode-specific considerations

---

## Config Dependency Matrix

These configs MUST be changed together. Changing one without adjusting the others creates bugs.

| Primary Change | Must Also Adjust | Why |
|----------------|------------------|-----|
| Lower `spawn-limits.monsters` | Lower `mob-spawn-range` | Lowering spawn limits without reducing spawn range = same density with fewer mobs = mobs still spawn near players but cap out faster elsewhere. Use the spawn-limit cheat sheet. |
| Lower `simulation-distance` | Lower `mob-spawn-range` AND `despawn-ranges.hard.horizontal` | Farms won't work, mobs won't despawn properly. See despawn range table. |
| Lower `view-distance` | Check `entity-tracking-range` is still reasonable | Low view + high tracking = invisible entities popping in. Low view + low tracking = entities appear too close. |
| Change `entity-activation-range` | Match `entity-tracking-range` to be >= activation | If tracking range < activation range, entities appear frozen until player is close enough to see them move. |
| Enable `alt-item-despawn-rate` | Check that junk items aren't part of farm workflows | Items like arrows, bones, string may be part of farm collection systems. |
| Set `per-player-mob-spawns: false` | Recalculate spawn-limits (they become global, not per-player) | Without per-player spawning, spawn-limits become multiplicative (70 x players = 700 entities). |
| Use Spigot (not Paper) | Recalculate spawn-limits | Spigot spawn-limits are multiplicative per player. Paper's per-player-mob-spawns makes them per-player. Same config value = very different entity counts. |
| Change server type (Paper <-> Spigot) | Review ALL configs | Paper overrides Spigot configs differently. `paper-global.yml` takes precedence over `spigot.yml` for entity ranges. |

---

## Quick Reference: Gamemode Decision Matrix

| Config | SMP/Survival | Lobby | Bedwars | Skyblock | Factions/PvP | Creative | Modded |
|--------|-------------|-------|---------|----------|-------------|-----------|--------|
| `view-distance` | 5-7 | 3-4 | 4-5 | 4-5 | 5-7 | 7-10 | 4-6 |
| `simulation-distance` | 4-6 | 0* | 4-6 | 4 | 4-6 | 0-4 | 4 |
| `spawn-limits.monsters` | 30-50 | 0 | 0 | 20-35 | 30-50 | 0 | 80% vanilla |
| `entity-activation-range.animals` | 16-24 | 0-4 | 0-4 | 16-24 | 24 | 0-4 | 24-32 |
| `entity-activation-range.monsters` | 24 | 0-4 | 0-4 | 16-24 | 24+ | 0-4 | 24-32 |
| `entity-activation-range.misc` | 8 | 0-4 | 4-8 | 8 | 8-12 | 0-4 | 8-16 |
| `entity-activation-range.villagers` | 16-24 | 0-4 | N/A | 16-24 | 16-24 | 0-4 | 24-32 |
| `merge-radius.item` | 3.0-4.0 | 5.0+ | 2.5-3.5 | 3.5-4.5 | 2.5-3.5 | 5.0+ | 2.5-3.5 |
| `merge-radius.exp` | 4.0-6.0 | 10.0+ | 4.0-5.0 | 5.0-6.0 | 3.0-4.0 | 10.0+ | 3.0-4.0 |
| `arrow-despawn-rate` | 200-600 | 20 | 100-200 | 200-600 | 300-600 | N/A | 200-600 |
| `max-entity-collisions` | 4-8 | 1 | >= 4 | 4-8 | 4-8 | 1 | 8+ |
| `hopper-transfer` | **8** | **8** | **8** | **8** | **8** | **8** | **8** |
| `doMobSpawning` | true | false | false | true/false | true | false | true |
| `doDaylightCycle` | true | false | depends | true/false | true | false | depends |
| `randomTickSpeed` | default | 0 | depends | default | default | 0 | depends |

* simulation-distance: 0 means no simulation at all. Paper uses `0` to disable ticking. On Spigot, view-distance controls both.

---

## Warning Labels Reference

When making recommendations, always apply these labels clearly:

| Label | Meaning |
|-------|---------|
| **[SAFE]** | Change improves performance with no gameplay impact for this gamemode. |
| **[LOW RISK]** | Minor trade-off. Players may notice subtle differences. |
| **[MODERATE RISK]** | Noticeable gameplay change. Test before deploying. |
| **[HIGH RISK]** | Significant gameplay impact. Only apply if performance is critical AND the gamemode can absorb the change. |
| **[NEVER]** | This change breaks core gameplay. Do not apply. |
| **[DEPENDS]** | Effect depends on specific server setup or plugins. Investigate before applying. |
| **[BRAKE WARNING]** | This config change is known to introduce bugs or desyncs. Apply with caution and test thoroughly. |

---

## Review Checklist Template

When reviewing a server config, work through this checklist systematically:

```
SERVER CONFIG REVIEW CHECKLIST
================================

Server Type: [SMP / Lobby / Bedwars / Skyblock / Factions / Creative / Modded / Other]
Platform: [Paper / Spigot / Folia / Canvas]
Version: [MC version]
Players: [peak / average]

[ ] 1. VIEW/SIMULATION DISTANCE
    - view-distance appropriate for gamemode?
    - simulation-distance >= 4 for gameplay worlds?
    - simulation-distance <= view-distance?
    - view-distance not > 8 for SMP?

[ ] 2. ENTITY RANGES (activation + tracking)
    - activation <= tracking for each category?
    - ranges appropriate for gamemode?
    - ranges <= (simulation-distance - 1) x 16?
    - tracking-range-y enabled (Paper)?

[ ] 3. SPAWN LIMITS + MOB SPAWN RANGE
    - spawn-limits appropriate for player count?
    - mob-spawn-range <= simulation-distance - 1?
    - mob-spawn-range >= 3?
    - Using per-player-mob-spawns (Paper)?
    - Density calculation correct?

[ ] 4. MERGE RADIUS
    - merge-radius.item appropriate for gamemode?
    - merge-radius.exp appropriate?
    - Not too high for SMP/Bedwars/Skyblock?

[ ] 5. DESPAWN RANGES (Paper)
    - hard.horizontal >= 36?
    - hard.horizontal = (sim-dist - 1) x 16?
    - vertical at default (128)?

[ ] 6. HOPPER SETTINGS
    - hopper-transfer = 8? [NEVER CHANGE]
    - hopper-amount = 1? [NEVER CHANGE]

[ ] 7. ENTITY LIMITS
    - entity-per-chunk-save-limit set?
    - alt-item-despawn-rate enabled?
    - max-entity-collisions >= 3? [NEVER < 3]

[ ] 8. GAMERULES
    - doMobSpawning appropriate for gamemode?
    - doDaylightCycle appropriate?
    - randomTickSpeed appropriate?

[ ] 9. JVM FLAGS
    - Xms = Xmx?
    - Using appropriate GC (G1GC or ZGC)?
    - No bad flags present?
    - Heap size appropriate for player count?

[ ] 10. PER-WORLD CONFIGS
     - Nether/end have reduced view-distance?
     - Resource worlds have reduced spawns?
     - Lobby world has aggressive optimization?
     - Arena worlds have appropriate entity settings?

[ ] 11. BUG-CONFIG CHECK
     - No dangerous hopper-transfer values?
     - No dangerously low max-entity-collisions?
     - simulation-distance not 0 on gameplay worlds?
     - despawn-ranges not too aggressive?
     - tick-inactive-villagers not breaking farms?
     - merge-radius not breaking item collection?

[ ] 12. DEPENDENCY CHECK
     - spawn-limits + mob-spawn-range consistent?
     - activation-range + tracking-range consistent?
     - All per-world overrides consistent with defaults?
     - Spigot values properly overridden by Paper?
```