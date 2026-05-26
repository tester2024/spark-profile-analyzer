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
| `-XX:+UseZGC` | N/A | Use for servers with >24GB heap or JDK 21+ | RECOMMENDED | Generational ZGC (JDK 21+) is excellent for large servers. |
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