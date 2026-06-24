# CPU Usage Analysis

How to interpret CPU data from Spark profiler, identify bottlenecks, and make optimization decisions.

---

## Interpreting Process vs System CPU

### Definitions

| Metric | What it measures | How Spark reports it |
|--------|-----------------|---------------------|
| Process CPU% | CPU time used by the JVM process across ALL threads | Usually shown as aggregate or per-thread |
| System CPU% | Total CPU usage across the entire machine | Includes all processes, kernel, I/O wait |

### Understanding Process CPU on Multi-Core

Process CPU% can exceed 100% on multi-core systems:

| Process CPU% | On 4-core system | On 8-core system |
|-------------|-----------------|-----------------|
| 25% | 1 core at 25% (or 1 thread ≈ ¼ core) | 1 core at 25% |
| 100% | 1 core fully used | 1 core fully used |
| 200% | 2 cores fully used | 2 cores fully used |
| 400% | All 4 cores fully used | 4 cores fully used |
| 800% | Not possible (max = 400%) | All 8 cores fully used |

**Formula**: Max process CPU = cores × 100%

---

## CPU Saturation Patterns

### Pattern: High Process CPU (> 80% of a core)

| Cause | Symptoms | How to Verify | Fix |
|-------|----------|-------------|-----|
| Main thread overloaded | MSPT > 45ms, TPS < 20 | Spark shows main thread at 90%+ | Reduce entity/chunk load, optimize plugins |
| Too many active entities | Entity tick time dominates Spark | Check entity count in Spark | Lower spawn limits, activation range |
| Expensive plugin | Specific plugin package hot in Spark | Call tree shows plugin methods | Report to dev, find alternative |
| GC overhead | GC time > 10% of profile | Spark GC section shows high total time | Increase heap, tune GC flags |

### Pattern: High System CPU, Lower Process CPU

| Cause | Symptoms | How to Verify | Fix |
|-------|----------|-------------|-----|
| Another process competing | System CPU > process CPU + margin | `top`/`htop` shows other processes | Kill or limit competing processes |
| High kernel/I/O overhead | System CPU higher than expected | `iostat` shows high disk I/O | Faster storage, reduce disk writes |
| Network interrupt load | High system CPU during player joins | `softirq` time in `/proc/stat` | Use larger network buffers, RSS |
| Hypervisor overhead | High system CPU on VM | CPU steal time in `top` | Better host or dedicated hardware |

### Pattern: Low CPU but High Lag

This is a crucial case - CPU is not the bottleneck.

| Cause | Symptoms | How to Verify | Fix |
|-------|----------|-------------|-----|
| Lock contention | Threads waiting, not CPU | Spark shows blocked threads, low CPU | Reduce synchronized blocks, use concurrent collections |
| I/O wait | Low CPU, high iowait | `iowait` in `top`, slow disk | Faster SSD, reduce disk operations |
| Network bound | Low CPU, lag on mass events | Packet queue growing | Optimize packet handling, bandwidth |
| Sleep/block in tick loop | Main thread sleeping unnecessarily | Spark shows unexpected sleep in tick | Fix plugin causing sleep/yield in main thread |

---

## CPU Steal on Virtualized Hosts

### What CPU Steal Is

On virtualized servers (VPS, cloud), the hypervisor allocates CPU time among virtual machines. When other VMs on the same physical host demand CPU, the hypervisor may "steal" time from your VM.

### Detection

| Tool | Command | What to Check |
|------|---------|--------------|
| `top` | Look at `st` column | CPU steal percentage |
| `vmstat` | `vmstat 1 5` | `st` column |
| Spark | System CPU vs process CPU gap | If system CPU is much higher than your process |

### Thresholds

| Steal % | Rating | Impact | Action |
|---------|--------|--------|--------|
| 0-2% | GOOD | Normal virtualization overhead | None |
| 2-5% | OK | Minor contention | Monitor during peak times |
| 5-10% | WARNING | Host overcommitted | Contact provider, consider upgrade |
| 10-20% | CRITICAL | Significant CPU time lost | Switch providers or get dedicated CPU |
| > 20% | EMERGENCY | Server severely impacted | Immediate: change hosting |

**Important**: CPU steal cannot be fixed by JVM tuning. The only fix is getting better hosting (dedicated CPU, less oversold node).

---

## Thread-Level CPU Attribution

### Key Threads in Minecraft Server

| Thread | Purpose | Normal CPU% | Warning CPU% | Critical CPU% |
|--------|---------|------------|-------------|---------------|
| Server Main Thread | Game tick, entity processing | 30-60% of 1 core | 60-80% | > 80% |
| Netty I/O (1-4 threads) | Network packet I/O | 5-15% each | 15-40% | > 40% |
| Chunk I/O threads | Async chunk load/save | 5-20% each | 20-50% | > 50% |
| GC threads | Garbage collection | 5-20% total | 20-40% | > 40% |
| Scheduled Pool | Plugin async tasks | 5-15% total | 15-30% | > 30% |
| Region threads (Folia only) | Per-region tick processing | 20-50% each | 50-70% | > 70% |

### Identifying Thread Imbalance

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| Main thread at 90%, others at 10% | Single-threaded bottleneck | Consider Folia for parallelism |
| Chunk I/O at 80% | Slow storage or too many chunk loads | SSD upgrade, pre-generate, reduce view-distance |
| Netty threads at 70% | Network load high | More Netty threads (usually auto), check packet volume |
| GC threads consistently at 40%+ | Memory pressure | Increase heap, tune GC |
| One async thread at 100% | Plugin with busy-loop or infinite task | Profile and report to plugin dev |

---

## CPU Context Switching Overhead

### What Context Switching Is

When the OS switches between threads, it saves/restores register state. With many active threads, this overhead becomes measurable.

### Context Switch Thresholds

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| Context switches/sec | < 10,000 | 10,000-50,000 | > 50,000 |
| Context switches per CPU/sec | < 2,500 | 2,500-10,000 | > 10,000 |

### Measuring (Linux)

```bash
# Per-process context switches
cat /proc/<pid>/status | grep voluntary_ctxt_switches
cat /proc/<pid>/status | grep nonvoluntary_ctxt_switches

# System-wide
vmstat 1 5    # cs column
```

### Reducing Context Switches

| Strategy | Impact | How |
|----------|--------|-----|
| Reduce thread count | High | Don't oversize thread pools; use optimal sizing |
| Use NIO/epoll | Medium | Ensure Netty uses native transport (auto on Linux) |
| Avoid lock contention | High | Use concurrent collections, lock-free algorithms |
| Increase time slice | Low | Nice the process, use CPU affinity |
| CPU affinity | Medium | Pin critical threads to specific cores |

### Thread Pool Sizing Impact

| Thread Pool Type | Too Few Threads | Too Many Threads | Optimal |
|-----------------|-----------------|------------------|---------|
| Chunk I/O | Slow chunk loading | Context switch + memory overhead | 2-4 threads |
| Scheduled pool | Tasks queued, delayed | Context switch overhead | 2-4 threads |
| Netty worker | Packet processing delay | Context switch overhead | CPU cores (auto) |
| Async task pools | Task backlog | Context switch + memory overhead | 4-8 threads |

---

## Correlation Between CPU Usage and TPS/MSPT

### The Fundamental Relationship

On a single-threaded server (non-Folia):

```
TPS = 1000 / max(MSPT, 50)
MSPT ≈ tick_work_time / 1_core_throughput
```

The main thread processes ALL game logic. CPU usage of the main thread directly predicts MSPT.

### Expected CPU-TPS Relationship (Main Thread)

| Main Thread CPU (1 core) | Expected MSPT | Expected TPS |
|-------------------------|--------------|--------------|
| 20% | ~10ms | 20 (healthy) |
| 40% | ~20ms | 20 (fine) |
| 60% | ~30ms | 20 (okay) |
| 80% | ~40ms | 18-20 (tight) |
| 90% | ~45ms | 17-19 (warning) |
| 95%+ | ~50ms+ | < 18 (problem) |
| 100% (sustained) | 50ms+ | < 15 (critical) |

### When CPU Does NOT Predict TPS

| Scenario | Why CPU Doesn't Predict TPS | What to Check Instead |
|----------|---------------------------|----------------------|
| GC pauses | CPU may be low when GC pauses (or high during concurrent GC) | GC pause time directly |
| I/O bound | CPU waiting on disk/network | I/O wait time, disk latency |
| Lock contention | CPU not used while threads wait | Lock wait time, blocked thread count |
| Sleep/yield | Thread voluntarily sleeping | Spark sleep percentage |
| Large heap with G1GC | GC using CPU but not blocking main thread (concurrent mark) | Only STW pause time |

---

## When CPU Is Not the Bottleneck

### I/O-Bound Servers

| I/O Type | Symptom | Diagnosis | Fix |
|----------|---------|-----------|-----|
| Disk I/O (chunk loading) | High iowait, slow chunk loads | `iowait` in top, `iostat -x 1` | SSD, pre-generate, reduce view-distance |
| Disk I/O (saving) | Periodic lag on auto-save | MSPT spikes at save interval | Increase save interval, async saves |
| Network I/O | High bandwidth, packet queue | Netty thread CPU, packet counts | Larger `network-compression-threshold`, reduce entity tracking range |

### Lock Contention

| Symptom | How to Identify | Common Cause | Fix |
|---------|----------------|-------------|-----|
| Threads wait but CPU low | Thread dumps show BLOCKED state | synchronized blocks on shared resources | Use ConcurrentHashMap, ReadWriteLock |
| Main thread appears idle | Spark shows main thread low CPU but MSPT high | Main thread waiting on external call | Make calls async, don't block main thread |
| Periodic stalls | Consistent short pauses | Lock acquired periodically (e.g., chunk lock) | Reduce lock scope, use optimistic locking |

### Memory-Bound (GC-Driven, Not CPU-Driven)

| Symptom | Cause | Fix |
|---------|-------|-----|
| Periodic TPS drops not correlated with CPU spikes | GC STW pauses | Increase heap, tune GC |
| CPU low but MSPT high | GC pausing threads | Check GC log for pause times |
| GC CPU high, but no lag | Concurrent GC working (normal for ZGC) | Not a problem - concurrent work doesn't stall app |

---

## Thread Pool Sizing Recommendations

### General Formula

```
CPU-bound pool: threads = CPU cores + 1
I/O-bound pool: threads = CPU cores × 2 (or more for high-latency I/O)
```

### Minecraft-Specific Pool Sizes

| Pool | Recommended Size | Rationale |
|------|-----------------|-----------|
| Server main thread | 1 | Fixed by Minecraft design |
| Chunk load I/O | 2-4 | I/O bound but not highly parallel |
| Chunk generation | 4-8 | CPU bound per region |
| Netty workers | auto (=CPU cores) | Let Netty auto-detect |
| Scheduled executor | 2-4 | Most tasks are short |
| Async entity processing | N/A on standard | Use Folia for entity parallelism |
| GC threads | auto | JVM auto-detects based on cores |

### Impact of Oversized Pools

| Pool Size Problem | Symptom | Impact |
|------------------|---------|--------|
| Too many I/O threads | Memory overhead from buffers, context switching | 10-20% performance loss |
| Too many scheduled threads | Context switching, scheduling overhead | 5-15% performance loss |
| Too many Netty threads | Context switching, lock contention on shared buffers | 5-10% performance loss |
| Too few chunk I/O | Slow chunk loading, players see void | Player experience |

### Thread Priority Considerations

| Thread | Recommended Priority | Reason |
|--------|---------------------|--------|
| Server main tick thread | Normal (OS default) | Don't mess with this. |
| GC threads | Normal | JVM manages internally. |
| Chunk I/O | Below normal | Chunk loading less critical than ticking. |
| Scheduled/async | Below normal | Should not preempt main thread. |
| Netty I/O | Normal | Timely packet processing affects all players. |

---

## CPU Monitoring Commands (Reference)

| Platform | Command | Purpose |
|----------|---------|---------|
| Linux | `top -H -p <pid>` | Per-thread CPU for Java process |
| Linux | `htop` | Visual CPU core view |
| Linux | `mpstat -P ALL 1` | Per-core CPU statistics |
| Linux | `pidstat -t -p <pid> 1` | Per-thread CPU for a process |
| Linux | `vmstat 1` | System-wide context switches, CPU |
| Linux | `iostat -x 1` | Disk I/O utilization |
| Linux | `cat /proc/cpuinfo` | CPU info, core count |
| Windows | `typeperf "\Processor(*)\% Processor Time"` | Per-core usage |
| Windows | `typeperf "\Process(java)\% Processor Time"` | Process CPU |
| Any | Spark profiler | Thread-level attribution within JVM |