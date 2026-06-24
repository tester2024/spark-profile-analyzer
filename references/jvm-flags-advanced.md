# Advanced JVM Flags Reference for Minecraft Servers

Comprehensive reference for JVM flags commonly used with Minecraft servers, covering Paper/Folia/Canvas, Spigot, and proxies. Includes flag-by-flag analysis with recommended values, warnings, and best practices.

---

## Flag Categories

| Category | Description |
|---|---|
| **RECOMMENDED** | Generally beneficial for Minecraft servers. Safe to use. |
| **OPTIONAL** | May help specific workloads. Test before deploying. |
| **WARNING** | Can cause issues if misconfigured. Requires careful tuning. |
| **NOT RECOMMENDED** | Known to cause problems with Minecraft. Avoid. |
| **CONTEXT-DEPENDENT** | Depends on server type, JDK version, or hardware. |

---

## GC Flags

See `jvm-gc-tuning.md` for detailed GC analysis.

| Flag | Default | Recommended | Category | Notes |
|---|---|---|---|---|
| `-XX:+UseG1GC` | JDK 9+ default | Use for servers with 4-32GB heap | RECOMMENDED | Aikar's G1GC flags are the gold standard for Minecraft. |
| `-XX:+UseZGC` | N/A | Consider at 16GB+, recommend at 24GB+, mandatory at 32GB+ | RECOMMENDED | Generational ZGC (JDK 21+) is excellent for large servers. See the ZGC-vs-G1GC decision table in `jvm-gc-tuning.md`. |
| `-XX:+UnlockExperimentalVMOptions` | N/A | Required for ZGC on JDK < 21 | CONTEXT | Needed to enable ZGC on older JDKs. Not needed on JDK 21+. |
| `-XX:+UnlockDiagnosticVMOptions` | N/A | Required for some diagnostic flags | OPTIONAL | Required for `+PrintGCDetails`, `+PrintGCDateStamps` etc. Not needed for production tuning. |
| `-XX:SoftMaxHeapSize` | N/A | Set to 75-85% of Xmx with ZGC | RECOMMENDED (ZGC only) | Helps ZGC balance memory usage. Set to e.g. `18G` with `Xmx30G`. |
| `-XX:-ZUncommit` | N/A | Recommended to disable with ZGC | RECOMMENDED (ZGC) | Prevents heap shrinking which causes performance dips. |
| `-XX:+UseStringDeduplication` | N/A | Good with G1GC, automatic with ZGC | OPTIONAL (G1GC) | Reduces memory for duplicate strings. Slightly increases GC pause time with G1GC. |

---

## Memory & Heap Flags

| Flag | Default | Recommended | Category | Notes |
|---|---|---|---|---|
| `-Xms` | Platform-dependent | **Must equal Xmx** | RECOMMENDED | Prevents heap resizing and fragmentation. Always set Xms = Xmx. |
| `-Xmx` | Platform-dependent | Based on player count | RECOMMENDED | See memory sizing in `jvm-gc-tuning.md`. 4-8GB for small, 8-16GB for medium, 16-32GB for large. |
| `-XX:+AlwaysPreTouch` | false | true | RECOMMENDED | Pre-touches all heap pages at startup. Eliminates page fault stalls during runtime. Essential for production. |
| `-XX:+UseTransparentHugePages` | false | true on Linux only | WARNING | Can improve performance on Linux. Requires OS THP support (madvise mode). **DO NOT USE on Windows/macOS** - no effect or crashes. |
| `-XX:+UseCompactObjectHeaders` | false (JDK 21+) | true for memory savings | OPTIONAL | Reduces object header size from 16 bytes to 12 bytes, saving ~5-15% heap. **JDK 21+ only.** May have compatibility issues. Test before production. |
| `-XX:SoftRefLRUPolicyMSPerMB` | 1000 | 1000 or 2000 | WARNING | Controls how long soft references survive. Default 1000 is fine. Values < 1000 aggressively clear caches (LevelDB, plugin caches). Values > 10000 keep refs too long. |
| `-XX:AutoBoxCacheMax` | 128 | 10000-20000 for servers | OPTIONAL | Caches Integer/Long values up to this number. Minecraft uses many boxed numbers. 10000-20000 is reasonable. Higher = more memory, slightly better performance. |
| `-XX:+UseLargePages` | false | true only if OS configured | WARNING | Use large/huge memory pages for the heap (reduces TLB misses). **Requires OS-level huge-page reservation, else JVM aborts at startup with "Large pages failed" or falls back silently.** On Linux: reserve 2 MB huge pages (`/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages`) and mount hugetlbfs; on Windows: configure "Lock pages in memory" + Boot-time huge-page allocation. See the [Large Pages](#large-pages) section below. Prefer `-XX:+UseLargePagesInMetaspace` paired with this for metaspace. ZGC supports large pages (see ZGC wiki). |
| `-XX:LargePageSizeInBytes=2M` | OS-dependent | 2M on Linux x86 | CONTEXT | Explicitly sets the large page size the JVM should request. On Linux x86_64 the only hardware huge-page size is **2 MB** (1 GB transparent-hugepages are rarely usable by the JVM). On Windows this is auto-negotiated; setting it explicitly can help when multiple page sizes are available (e.g. AMD64 servers offering 2 MB and 1 GB). Must match a size the OS has reserved, otherwise large-page allocation fails. Leave unset to let JVM auto-detect. |
| `-XX:+UseDynamicNumberOfGCThreads` | false (G1)/true (ZGC since 17) | true | RECOMMENDED (ZGC) | Lets the GC dynamically scale the number of GC threads up/down based on workload instead of pinning to `ParallelGCThreads`. **For ZGC, this is the default since JDK 17** (the heuristic usually works well); harmless to set explicitly. For G1GC, enabling can help small heaps avoid over-scheduling. Do NOT combine with a manually pinned low `ParallelGCThreads` -- choose one strategy. |

---

## JIT Compiler Flags

| Flag | Default | Recommended | Category | Notes |
|---|---|---|---|---|
| `-XX:CICompilerCount` | max(log2(CPUs), 1) | 4-8 for most servers | CONTEXT | Number of JIT compiler threads. **Must not exceed CPU core count.** For Minecraft's single-thread-heavy workload, 4-8 is usually optimal. Higher = more CPU overhead for compilation. |
| `-XX:+UseCriticalCompilerThreadPriority` | false | Can enable | OPTIONAL | Gives JIT compiler threads higher OS priority. Helps ensure hot code gets compiled quickly. Only effective on Linux with proper permissions. |
| `-XX:+UseCriticalJavaThreadPriority` | false | Can enable | OPTIONAL | Gives critical Java threads (GC, compiler) higher OS priority. Only effective on Linux with root or CAP_SYS_NICE. No effect on Windows. |
| `-XX:+SegmentedCodeCache` | false (JDK < 23) | true | RECOMMENDED | Enables segmented code cache with separate profiled and non-profiled regions. Improves JIT efficiency and reduces code cache fragmentation. |
| `-XX:ReservedCodeCacheSize` | 240MB | 512-784MB | CONTEXT | Total code cache size. 512MB for medium servers, 784MB for large/modded. Going beyond 1GB wastes memory. |
| `-XX:NonProfiledCodeHeapSize` | auto | 256-512MB | CONTEXT | Size of the non-profiled code heap (for fully optimized code). If using SegmentedCodeCache, set to ~60% of ReservedCodeCacheSize. |
| `-XX:ProfiledCodeHeapSize` | auto | 128-256MB | CONTEXT | Size of the profiled code heap (for warming-up code). Smaller than non-profiled. ~30% of ReservedCodeCacheSize. |
| `-XX:-DontCompileHugeMethods` | true (don't compile) | -DontCompileHugeMethods (enable compilation) | OPTIONAL | Disabling DontCompileHugeMethods allows the JIT to compile very large methods. Can improve peak performance for complex code paths. |
| `-XX:MaxInlineLevel` | 9 | 15-20 | RECOMMENDED | Maximum depth of inlined method calls. 15-20 is good for Minecraft. Values > 20 rarely help and increase compilation time. **Velocity proxy**: use 15. |
| `-XX:MaxInlineSize` | 35 | 200-270 | OPTIONAL | Maximum bytecode size of a method to inline. Higher = more inlining but more code cache usage. Values above 300 are excessive. |
| `-XX:FreqInlineSize` | 325 | 2000-3000 | CONTEXT | Maximum bytecode size of a frequently-called method to inline regardless of size. Only applies to hot methods. 2000-3000 for tuned servers. |
| `-XX:InlineSmallCode` | 2000 | 2000-3000 | OPTIONAL | Size threshold for inlining already-compiled small methods. Higher = more inlining. Default 2000 (bytes) is reasonable. |
| `-XX:LoopUnrollLimit` | 60 | 60-100 | CONTEXT | Maximum number of instructions in an unrolled loop. Increasing slightly can help vectorized loops. Values above 100 rarely help. Default 60 is fine for most cases. |
| `-XX:+UseSuperWord` | true | keep enabled | RECOMMENDED | Enables SIMD vectorization. Should be left ON for all servers. Provides ~10-20% performance boost for vectorizable loops. |
| `-XX:+UseVectorMacroLogic` | false (JDK 23+) | true | OPTIONAL (JDK 23+) | Combines multiple scalar operations into SIMD vector operations. JDK 23+ only. Experimental. |
| `-XX:+UseFMA` | false | Can enable | OPTIONAL | Uses FMA (Fused Multiply-Add) instructions. Small performance gain for math-heavy code. Requires CPU support (Haswell+/Zen+). |
| `-XX:+UseCMoveUnconditionally` | false | Can enable | OPTIONAL | Converts branches to conditional moves. Can reduce branch mispredictions. Minor effect. |
| `-XX:+UseVectorCmov` | false | Can enable | OPTIONAL (JDK 21+) | Enables vectorized conditional-move (CMOV) intrinsics in the JIT's super-word (SIMD) optimizer. Unlike `UseCMoveUnconditionally` (which converts *scalar* branches to CMOV), this targets *vector* comparisons/block updates produced by `UseSuperWord`. Improves autovectorizable loops but can lengthen compile time. Test before production; rare regressions on unvectorizable code paths. |
| `-XX:+AlwaysActAsServerClassMachine` | false | Can enable | OPTIONAL | Forces the JVM to use server-class defaults (ergonomics). Usually unnecessary on 64-bit JVMs which default to server class. |

---

## CPU & Thread Flags

| Flag | Default | Recommended | Category | Notes |
|---|---|---|---|---|
| `-XX:ActiveProcessorCount` | Actual cores | Match actual cores | CONTEXT | **Must match actual CPU cores/threads.** Override for containers where JVM misdetects cores. Setting higher than actual = thread oversubscription. Setting lower = wastes cores. For VPS with 4 vCPUs, set to 4. |
| `-XX:UseAVX` | Auto-detect | 2 for broad compatibility | WARNING | UseAVX=3 requires AVX-512 which is NOT available on all CPUs. **Setting AVX=3 on unsupported CPUs causes JVM crash with UnsupportedHardwareException.** Use AVX=2 for broad compatibility (Sandy Bridge+, Zen+). Most Minecraft servers don't benefit significantly from AVX-512 vs AVX2. |

---

## System Property Flags

| Flag | Default | Recommended | Category | Notes |
|---|---|---|---|---|
| `-Dlog4j2.formatMsgNoLookups=true` | false | true | RECOMMENDED | Mitigates Log4Shell (CVE-2021-44228). **Required on all servers running Java 8-17.** JDK 18+ patched this at the JDK level. |
| `-Dfile.encoding=UTF-8` | Platform-dependent | UTF-8 | RECOMMENDED | Ensures consistent string handling. Required for many Minecraft plugins that expect UTF-8. |
| `-Djava.security.egd=file:/dev/urandom` | /dev/random | file:/dev/urandom on Linux | RECOMMENDED (Linux) | Speeds up SecureRandom initialization. On Linux, `/dev/random` blocks when entropy is low. Use `/dev/urandom` for faster startup. **Not needed on Windows.** |
| `-Duser.timezone=UTC` | System TZ | Set to your TZ | RECOMMENDED | Ensures consistent timezone. Set to your server's timezone or UTC for logs. Prevents timezone-related bugs. |
| `-Dnet.kyori.ansi.colorLevel=truecolor` | auto | truecolor | OPTIONAL | Kyori adventure color support. Set to `truecolor` for modern terminals, `256` for basic color, or `16` for limited color. |
| `-Dterminal.jline=false` | auto | false for non-interactive | CONTEXT | Disable JLine terminal handling. Set to true for interactive console, false for scripts/Docker. |
| `-Dterminal.ansi=true` | auto | true | OPTIONAL | Enable ANSI colors in console output. |
| `--add-modules=jdk.incubator.vector` | N/A | Required for Canvas/Folia | RECOMMENDED (Canvas/Folia) | Required by Canvas and modern Folia for SIMD vector operations. **Must include** for Canvas/Folia servers. |
| `-XX:+PerfDisableSharedMem` | false | true | RECOMMENDED | Disables writing JVM perf data to `/tmp/hsperfdata_<user>/`. This file is normally used by `jstat`/`jcmd` to attach to a running JVM. Disabling it (a) plugs a small information-disclosure hole on shared hosts (other users on the box could otherwise read the perf file), and (b) avoids tiny disk-write overhead. **Side effect:** local tools that need to attach (`jstat`, `jcmd`, VisualVM auto-discovery) cannot discover the JVM via the shared mem file -- you must use `<pid>` explicitly (e.g. `jcmd <pid> GC.class_histogram`). For a production MC server this is usually desirable. |
| `-Xlog:gc*:file=<path>:time,uptime:filecount=N,filesize=M` | none | enable | RECOMMENDED | Unified JVM GC logging (replaces the old `-XX:+PrintGCDetails` etc.). `gc*` = all GC-tagged messages; decorate with `time,uptime`; rotate through `filecount` files of `filesize` each. Example: `-Xlog:gc*:file=GClogs/gc.log:time,uptime:filecount=10,filesize=50M` keeps 10 rolling 50 MB logs -- ideal for long-running servers. See [GC Logging](#gc-logging-xlog) below. |

---

## Memory Management Flags

| Flag | Default | Recommended | Category | Notes |
|---|---|---|---|---|
| `-XX:+UseStringDeduplication` | false | Yes for G1GC, automatic for ZGC | OPTIONAL (G1GC) | Reduces memory by deduplicating String objects. Slight GC overhead with G1GC. ZGC handles this automatically. |
| `-XX:-ZUncommit` | ZGC uncommits | Disable (recommended) | RECOMMENDED (ZGC) | Prevents ZGC from shrinking heap. Uncommit causes performance dips when heap needs to re-grow. Always disable for Minecraft. |
| `-XX:SoftRefLRUPolicyMSPerMB` | 1000 | 1000-2000 | CONTEXT | See Memory & Heap Flags above. |
| `-XX:+AlwaysPreTouchStacks` | false | Can enable | OPTIONAL (JDK 23+) | Pre-touches thread stacks. Similar to AlwaysPreTouch but for stacks. Reduces allocation stalls for thread creation. JDK 23+ only. |

---

## Bad Flags to Avoid

| Flag | Why It's Bad | Instead Use |
|---|---|---|
| `-XX:+UseParallelGC` | STW pauses kill TPS. Worst GC for Minecraft. | G1GC (Aikar's flags) or ZGC |
| `-XX:+UseConcMarkSweepGC` | Deprecated. Removed in newer JDKs. | G1GC or ZGC |
| `-XX:+UseG1GC` with no other flags | Default G1GC is acceptable but sub-optimal. | Aikar's G1GC flags or ZGC |
| `-Xms != -Xmx` | Heap fragmentation from resizing. Always set equal. | Set `-Xms` = `-Xmx` |
| `-XX:G1HeapRegionSize` too small | Causes humongous object allocation | Set based on heap size: 8M for 8-32GB, 16M for 32+GB |
| `-XX:+AggressiveOpts` | Unstable optimizations. Can cause JIT deoptimization storms. | Remove it entirely |
| `-XX:+UseFastAccessorMethods` | Removed in modern JDKs. No effect. | Remove |
| `-XX:+UseAdaptiveSizePolicy` | Can override G1GC region sizing | Remove with G1GC |
| `-XX:ParallelGCThreads` too high | Excess threads waste CPU. | Set to equal CPU cores for G1GC. |
| `-XX:ConcGCThreads` too high | Excess concurrent GC threads steal CPU. | Let JVM auto-detect (G1GC default: ~1/4 ParallelGCThreads) |

---

## Canvas/Folia-Specific Flags

Canvas and Folia (region-threaded) servers benefit from specific configurations due to their multi-threaded nature.

### Required for Canvas

| Flag | Why | Notes |
|---|---|---|
| `--add-modules=jdk.incubator.vector` | Required for SIMD operations | Missing this causes startup failure on Canvas. |
| `-XX:+UseCompactObjectHeaders` | Reduces memory per object | JDK 21+ only. Saves 5-15% heap. Test for compatibility. |

### Recommended for Folia/Canvas

| Flag | Value | Why |
|---|---|---|
| `-XX:CICompilerCount` | 4-8 | Folia uses many threads. 4-8 compiler threads is usually sufficient. |
| `-XX:+SegmentedCodeCache` | N/A | Reduces code cache fragmentation with many threads. |
| `-XX:+UseSuperWord` | N/A | SIMD vectorization helps region threading. |
| `-XX:+UseTransparentHugePages` | N/A | Linux only. Reduces TLB misses with many threads. |

### Folia/Canvas Thread Pool Sizing

| Pool | Recommended | Notes |
|---|---|---|
| Region threads | CPU cores - 2 | Left for I/O and Netty. More doesn't help if regions aren't spread. |
| I/O threads | 2-4 | Chunk I/O. |
| Netty threads | 4-8 | Network processing. |

---

## Large Pages

<a id="large-pages"></a>

(`-XX:+UseLargePages`, `-XX:LargePageSizeInBytes=2M`, and companion `-XX:+UseLargePagesInMetaspace`.)

Large pages (a.k.a. huge pages on Linux) let the CPU's TLB (Translation Lookaside Buffer) cover more memory with fewer entries, cutting TLB-miss overhead -- meaningful on a 32 GB heap where the default 4 KB pages mean ~8 million page-table entries. This is *setup-heavy* but genuinely beneficial for big heaps; ZGC supports large pages natively (OpenJDK ZGC wiki: "Configuring ZGC to use large pages will generally yield better performance ... and comes with no real disadvantage, except that it's slightly more complicated to setup").

### When to enable
- Heap **≥ 8-16 GB** (TLB pressure scales with heap).
- You have **OS-level control** (root/admin) to reserve pages.
- Host is **not heavily oversubscribed** (reserved huge pages are pinned and unavailable to other guests -- a common foot-gun on shared hosts).

### Linux x86_64 setup (2 MB huge pages)

```bash
# 1. Reserve huge pages (persistent until reboot).
#    Heap 32 GB -> need 16384 pages of 2 MB. Reserve ~20-30% extra for non-heap JVM structures.
echo 20000 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages   # verify

# 2. Kernel >= 4.14 can skip the hugetlbfs mount. Older kernels:
mkdir /hugepages && mount -t hugetlbfs -o uid=$(id -u) nodev /hugepages

# 3. Launch JVM with large pages.
java -XX:+UseZGC -Xms32G -Xmx32G -XX:+UseLargePages -XX:LargePageSizeInBytes=2M -XX:+AlwaysPreTouch ...
```

For persistence across reboots, add the `nr_hugepages` setting to `sysctl.conf` / a systemd unit and the mount to `/etc/fstab`.

### Windows setup
- Grant the JVM service user **"Lock pages in memory"** (Group Policy -> Local Security Policy -> User Rights Assignment).
- Enable **Boot-time huge-page allocation** via registry/Hyper-V host config (Windows reserves pages only when configured ahead of boot).
- `-XX:+UseLargePages` will then negotiate 2 MB pages automatically. Leave `-XX:LargePageSizeInBytes` unset on Windows (the JVM auto-selects from available sizes).

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Large pages failed` / JVM falls back to small pages silently | Not enough pages reserved (or reserved by another process) | Re-run the `nr_hugepages` echo and re-verify |
| JVM refuses to start | No accessible hugetlbfs mount (old kernel) and `-XX:+UseLargePages` set | Mount hugetlbfs, **or** drop the flag |
| Other tenants on the box starve | Huge pages are pinned RAM | Use **transparent huge pages** (`-XX:+UseTransparentHugePages`) instead -- madvise-style, no reservation |
| Want metaspace on large pages too | Not covered by `UseLargePages` alone | Add `-XX:+UseLargePagesInMetaspace` (already in Aikar's flags) |

### Large pages vs transparent huge pages

| Approach | Pros | Cons |
|---|---|---|
| `-XX:+UseLargePages` (explicit huge pages) | Guaranteed, predictable latency | Reservation required, pages are pinned, harder on shared hosts |
| `-XX:+UseTransparentHugePages` (THP, Linux only) | Zero reservation, coexists with other tenants | Requires kernel `madvise` mode; weaker guarantee; can defrag in background causing stalls |

> Recommendation for a dedicated Minecraft host with **≥16 GB heap**: reserve explicit huge pages and use `-XX:+UseLargePages`. On shared/VPS hosts: use `-XX:+UseTransparentHugePages` and **do not** reserve huge pages.

---

## GC Logging (`-Xlog`)

Unified JVM logging replaces the legacy `-XX:+PrintGCDetails` / `-XX:+PrintGCDateStamps` family. Format:

```
-Xlog:<tags>[:<output>][:<decorators>][:filecount=N,filesize=M]
```

- `<tags>` -- comma-separated tag selectors. `gc*` = every tag combination containing `gc` (verbose, recommended for tuning); `gc` alone = one line per collection (quieter); `gc+heap` etc. narrow further.
- `<output>` -- `file=path/to/gc.log` or `stdout`. Writing to a file offloads I/O from the console thread.
- `<decorators>` -- `time,uptime` prepends wall-clock + JVM uptime to each line. Other useful ones: `level`, `tags`, `pid`.
- Rotation -- `filecount=10,filesize=50M` keeps 10 rolling 50 MB logs (500 MB max disk).

### Recommended for a production Minecraft server

```
-Xlog:gc*:GClogs/gc.log:time,uptime:filecount=10,filesize=50M
```

The directory must exist (`mkdir GClogs`) before JVM launch. The path is **relative to the server's working directory** (same CWD as your startup script) -- verify in your runner script.

### What you can diagnose from GC logs

- **Pause time / TPS loss** -- the `Pause` lines give actual STW durations. Cross-reference with spark `gc` command.
- **Frequency** -- count `Garbage Collection (Warm|Young|Mixed|Old|Full)` events between timestamps.
- **Allocation stalls (ZGC)** -- `Allocation Stall` lines mean threads blocked waiting for GC; correlate with MSPT spikes.
- **OOM imminent** -- `To-space exhausted` / `Evacuation Failure` (G1) signals the heap can't relocate live objects.
- **Memory leak** -- old-gen occupancy that never drops after full collections.

### Verbose debugging variants

```
-Xlog:gc*,gc+heap=debug,gc+ergo*=trace:file=gc-debug.log:time,uptime:filecount=5,filesize=20M
# Adds heap resize events, ergonomic decisions, and per-region detail.
```

> Spark's `gc` command can ingest GC log context if you also capture heap state via `/spark health --upload`, but the GC log is your fallback when spark wasn't running during an incident.

---

## Sculptor-specific system properties

`Sculptor` is a closed/private Minecraft server software (Paper-family). Its launcher reads a few `-D` system properties that don't exist on upstream Paper. These flags are **specific to the Sculptor launcher/runtime**, not standard JVM or Paper flags -- the JVM treats unknown `-D` keys as no-ops, so they are safe to leave on other server software (they simply do nothing).

| Property | Typical value | Purpose |
|---|---|---|
| `-Dsculptor.minecraftVersion=26.1.2` | matches the Paper-API version line | Pins which Minecraft/Paper-API patch set Sculptor builds and binds against. Uses the Paper version scheme (`major.minor.patch` of the Paper release line -- e.g. `26.1.2`). Mismatch with the installed jar produces a version-fail startup guard. |
| `-Dsculptor.includeExperimental=true` | `true`/`false` | Opt-in to pulling **experimental** patches/features that Sculptor has staged but not yet marked stable. Equivalent to opting into a "snapshot" branch of optimizations. Can include behavior-changing perf patches; disable before filing bug reports or comparing reproducibility with upstream Paper. |
| `-Ddump=true` | `true`/`false` | Tells the Sculptor launcher/build pipeline to **dump intermediate artifacts** -- typically the resolved patch series / compiled class dumps into the working directory. Used for debugging the build itself; enable only when inspecting Sculptor internals or generating a report for the maintainer; adds disk I/O at startup. |

> Since these are not OpenJDK or PaperMC flags, none of the standard JVM references document them. When auditing a startup script, recognize the `sculptor.` prefix as **launcher-specific configuration**, not a JVM tuning flag -- keep it out of any JVM-flag assessment table.

---

## JVM Flag Assessment Template

When reviewing a server's JVM flags, check each flag against this table:

```
JVM FLAG REVIEW
=============================================================

[✓] GOOD: -XX:+UseZGC - Appropriate GC for large heap
[✓] GOOD: -Xms30G -Xmx30G - Xms equals Xmx
[✓] GOOD: -XX:+AlwaysPreTouch - Pre-touches heap pages
[✓] GOOD: -XX:+DisableExplicitGC - Prevents plugin-triggered full GC
[✓] GOOD: -XX:+ParallelRefProcEnabled - Parallel reference processing
[!] INFO: -XX:-ZUncommit - Prevents heap shrinking (recommended for ZGC)
[!] INFO: -XX:+UseStringDeduplication - Reduces memory with ZGC
[!] CHECK: -XX:ActiveProcessorCount=32 - Verify matches actual core count
[!] CHECK: -XX:UseAVX=3 - Verify CPU supports AVX-512. Use 2 if unsure.
[!] INFO: -XX:+UnlockDiagnosticVMOptions - Required for some diagnostic flags
[!] INFO: -XX:+UnlockExperimentalVMOptions - Required for ZGC on older JDKs
[!] INFO: -XX:+UseDynamicNumberOfGCThreads - Lets GC threads scale (default for ZGC since 17). OK.
[!] INFO: -XX:+UseLargePages - Verify OS huge-page reservation exists, else startup aborts/falls back
[!] INFO: -XX:LargePageSizeInBytes=2M - Matches Linux x86_64 hardware huge-page size
[!] INFO: -XX:+PerfDisableSharedMem - Disables hsperfdata file; use jcmd <pid> explicitly
[!] INFO: -Xlog:gc*:file=GClogs/gc.log:time,uptime:filecount=10,filesize=50M - Rotating GC log. Ensure dir exists.
[!] INFO: -XX:+UseVectorCmov - Vectorized CMOV (distinct from scalar UseCMoveUnconditionally). Test for regressions.
[!] INFO: -XX:+UseCompactObjectHeaders - JDK 21+ only. Saves 5-15% heap.
[!] INFO: -XX:+AlwaysActAsServerClassMachine - Forces server ergonomics. Usually no-op on 64-bit.
[!] INFO: -Dterminal.jline=false - Non-interactive console
[!] INFO: -Dterminal.ansi=true - ANSI colours enabled
[!] INFO: -Dsculptor.* - Sculptor launcher properties (not JVM/Paper flags); no-op elsewhere
[!] INFO: --add-modules=jdk.incubator.vector - Required for Canvas/Folia (noop on plain Paper)
[!] CHECK: -XX:SoftRefLRUPolicyMSPerMB=10000 - Very high. Consider 1000-2000.
[!] CHECK: -XX:CICompilerCount=8 - Ensure this matches or is less than CPU cores
[!] INFO: -XX:+SegmentedCodeCache - Good for code organization
[!] CHECK: -XX:ReservedCodeCacheSize=784m - Reasonable for large server
[!] CHECK: -XX:NonProfiledCodeHeapSize=512m + ProfiledCodeHeapSize=256m = 768m out of 784m code cache. Close to limit.
[!] CHECK: -XX:MaxInlineLevel=20 - Good for Minecraft. Default is 9.
[!] CHECK: -XX:MaxInlineSize=270 - Reasonable. Default is 35.
[!] CHECK: -XX:FreqInlineSize=3000 - High but acceptable. Default is 325.
[!] CHECK: -XX:InlineSmallCode=3000 - Reasonable. Default is 2000.
[!] CHECK: -XX:LoopUnrollLimit=100 - Slightly above default (60). Acceptable.
[!] CHECK: -XX:AutoBoxCacheMax=20000 - High but useful for Minecraft. Default 128.
[!] INFO: -XX:+UseFMA - Uses FMA instructions if CPU supports
[!] INFO: -XX:+UseCMoveUnconditionally - Reduces branch mispredictions
[!] INFO: -XX:+UseSuperWord - SIMD vectorization enabled (should stay ON)
[!] INFO: -XX:+UseVectorMacroLogic - Vector macro logic (JDK 23+)
[✓] GOOD: -Dlog4j2.formatMsgNoLookups=true - Log4Shell mitigation
[✓] GOOD: -Dfile.encoding=UTF-8 - Consistent encoding
[✓] GOOD: -Djava.security.egd=file:/dev/urandom - Fast random for Linux
[✓] GOOD: --add-modules=jdk.incubator.vector - Required for Canvas/Folia
```