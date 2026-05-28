#!/usr/bin/env python3
"""
Heap Dump Analyzer for Minecraft Servers

Analyzes Java heap dumps (.hprof files) to identify memory leaks,
excessive object retention, and memory usage patterns. Supports both
Windows and Linux.

This script requires jmap/jhat (JDK tools) or can parse hprof files
directly with the hprof parser. For best results, use with Eclipse MAT
or VisualVM output.

Usage:
    python3 heapdump_analyzer.py <heapdump_file> [options]

For full analysis, also use with spark_toolkit.py heap/plugin-heap data
to correlate CPU hotspots with memory pressure.

Dependencies:
    No external dependencies required for basic analysis.
    For advanced analysis, install:
      - Eclipse MAT (Memory Analyzer Tool) - recommended for large dumps
      - VisualVM - for interactive analysis
"""

import argparse
import json
import os
import re
import struct
import sys
import subprocess
import shutil
from collections import defaultdict
from pathlib import Path


HPROF_MAGIC = b"JAVA PROFILE\0"
HPROF_VERSIONS = {0: "1.0.2", 1: "1.0.3", 2: "1.0.4"}


def parse_hprof_info(path, max_size_mb=2048):
    file_size = os.path.getsize(path)
    if file_size > max_size_mb * 1024 * 1024:
        return {"error": f"HPROF file too large ({file_size / 1024 / 1024:.0f}MB > {max_size_mb}MB limit). Use Eclipse MAT or jmap -histo for large files."}
    with open(path, "rb") as f:
        data = f.read(min(file_size, 50 * 1024 * 1024))
    if not data.startswith(HPROF_MAGIC):
        return {"error": "Not a valid HPROF file. Magic bytes do not match."}
    import struct as _struct
    pos = len(HPROF_MAGIC)
    version_byte = data[pos] if pos < len(data) else 0
    pos += 1
    version = HPROF_VERSIONS.get(version_byte, f"unknown({version_byte})")
    null_pos = data.index(b'\0', pos) if b'\0' in data[pos:] else pos
    pos = null_pos + 1
    timestamp = 0
    if pos + 8 <= len(data):
        timestamp = _struct.unpack('>Q', data[pos:pos + 8])[0]
        pos += 8
    id_size = 4
    if pos + 4 <= len(data):
        id_size = _struct.unpack('>I', data[pos:pos + 4])[0]
        pos += 4
    result = {
        "format": "hprof",
        "version": version,
        "id_size": id_size,
        "timestamp": timestamp,
        "timestamp_human": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp / 1000)) if timestamp else "unknown",
        "file_size": file_size,
        "file_size_human": _format_bytes(file_size),
        "note": "Full HPROF parsing requires Eclipse MAT or jhat. Use 'jmap -histo:live <pid>' for histogram analysis, or 'heapdump_analyzer.py analyze --jmap-histogram <file>' for structured leak detection.",
    }
    return result


LEAK_PATTERN_THRESHOLDS = {
    "string_dominance_pct": 30,
    "byte_array_dominance_pct": 25,
    "class_dominance_pct": 15,
    "single_class_growth_pct": 20,
    "thread_local_leak_pct": 10,
}

MINECRAFT_LEAK_SIGNATURES = {
    "net.minecraft.world.entity.Entity": {
        "leak_type": "entity_leak",
        "description": "Entity objects accumulating - check entity activation ranges and per-chunk limits",
        "threshold_instances": 50000,
        "risk": "HIGH",
    },
    "net.minecraft.world.level.chunk.Chunk": {
        "leak_type": "chunk_leak",
        "description": "Chunk objects not being unloaded - check view-distance and chunk-load settings",
        "threshold_instances": 5000,
        "risk": "CRITICAL",
    },
    "net.minecraft.network.Connection": {
        "leak_type": "connection_leak",
        "description": "Connection objects not being cleaned up - potential netty channel leak or disconnect handling issue",
        "threshold_instances": 1000,
        "risk": "HIGH",
    },
    "net.minecraft.nbt.CompoundTag": {
        "leak_type": "nbt_bloat",
        "description": "NBT tags consuming excessive memory - check entity NBT data, tile entity data, and saved data",
        "threshold_pct": 15,
        "risk": "MEDIUM",
    },
    "net.minecraft.server.level.ServerLevel": {
        "leak_type": "world_leak",
        "description": "World/level objects - check for unloaded world references preventing GC",
        "threshold_instances": 50,
        "risk": "CRITICAL",
    },
    "java.lang.Thread": {
        "leak_type": "thread_leak",
        "description": "Thread objects accumulating - check for thread pool misconfiguration or thread-local leaks",
        "threshold_instances": 500,
        "risk": "HIGH",
    },
    "java.util.concurrent.ConcurrentHashMap": {
        "leak_type": "map_leak",
        "description": "Concurrent maps growing without bounds - common in plugin caches and player data stores",
        "threshold_pct": 10,
        "risk": "MEDIUM",
    },
    "java.util.HashMap": {
        "leak_type": "map_bloat",
        "description": "HashMap objects with high memory - check for unbounded caches in plugins",
        "threshold_pct": 15,
        "risk": "MEDIUM",
    },
    "io.netty.buffer.PoolArena": {
        "leak_type": "netty_buffer_leak",
        "description": "Netty buffer pool arenas not being released - direct buffer leak, check plugin network handlers",
        "threshold_instances": 200,
        "risk": "HIGH",
    },
    "io.netty.channel.DefaultChannelPipeline": {
        "leak_type": "netty_pipeline_leak",
        "description": "Netty channel pipeline objects not being GC'd - check for duplicate handlers and shaded libraries",
        "threshold_instances": 500,
        "risk": "HIGH",
    },
    "byte[]": {
        "leak_type": "byte_array_bloat",
        "description": "Large byte[] usage - common causes: packet buffers, plugin data serialization, RegionFile caches",
        "threshold_pct": 25,
        "risk": "MEDIUM",
    },
    "char[]": {
        "leak_type": "string_bloat",
        "description": "Large char[] usage - strings consuming excessive heap, check for String deduplication (-XX:+UseStringDeduplication)",
        "threshold_pct": 25,
        "risk": "LOW",
    },
    "java.lang.String": {
        "leak_type": "string_dominance",
        "description": "String objects dominating heap - enable UseStringDeduplication and check for String-heavy caches",
        "threshold_pct": 20,
        "risk": "LOW",
    },
}

COMMON_LEAK_PATTERNS = [
    {
        "pattern": "static_collection_leak",
        "description": "Static collections (Maps, Lists) holding references that prevent GC. Common in plugin singletons.",
        "signs": ["java.util.Collections$UnmodifiableMap", "java.util.Collections$SynchronizedMap", "HashMap instances growing"],
        "check": "Look for static Map/List fields in plugin classes that never get cleared.",
        "fix": "Use WeakHashMap, Caffeine cache with eviction, or periodic cleanup tasks.",
    },
    {
        "pattern": "thread_local_leak",
        "description": "ThreadLocal values not being removed, especially in thread pools. Each thread retains its own copy permanently.",
        "signs": ["java.lang.ThreadLocal$ThreadLocalMap", "Thread instances with large ThreadLocal maps"],
        "check": "Search heap for ThreadLocal$ThreadLocalMap entries. Check if thread pool threads have unexpected large values.",
        "fix": "Always call ThreadLocal.remove() when done. Use try-finally blocks. Consider using custom thread pool with afterExecute cleanup.",
    },
    {
        "pattern": "listener_leak",
        "description": "Event listeners registered but never unregistered. Plugin events accumulating callback objects.",
        "signs": ["Listener instances from unloaded plugins", "EventExecutor objects with dead classloader references"],
        "check": "Search for classloaders of uninstalled plugins that shouldn't exist. Check event handler lists.",
        "fix": "Always unregister listeners in onDisable(). Use plugin-aware event registration.",
    },
    {
        "pattern": "cache_without_eviction",
        "description": "Caches (HashMap, ConcurrentHashMap) without size limits or TTL. Grow indefinitely.",
        "signs": ["Large ConcurrentHashMap instances", "HashMap with many entries in plugin packages"],
        "check": "Look for Map implementations in plugin packages with 10000+ entries.",
        "fix": "Use Caffeine or Guava Cache with maximumSize(), expireAfterWrite(), or expireAfterAccess().",
    },
    {
        "pattern": "reference_queue_leak",
        "description": "SoftReference/WeakReference objects whose referents are never cleared because the ReferenceQueue is never drained.",
        "signs": ["java.lang.ref.SoftReference instances", "java.lang.ref.WeakReference with live referents"],
        "check": "Count SoftReference vs WeakReference vs PhantomReference. High SoftReference count keeps objects alive under moderate pressure.",
        "fix": "Switch SoftReference to WeakReference for caches. Set -XX:SoftRefLRUPolicyMSPerMB=1000 (or 2000).",
    },
    {
        "pattern": "classloader_leak",
        "description": "Plugin classloaders not being GC'd after plugin unload. Holds all plugin classes and static state.",
        "signs": ["Multiple instances of PluginClassLoader", "Classes from 'uninstalled' plugins still in heap"],
        "check": "Search for URLClassLoader instances. If a plugin was unloaded but its classloader persists, it's a leak.",
        "fix": "Ensure plugins properly clean up in onDisable(). Check for static references, thread locals, and listener registrations.",
    },
    {
        "pattern": "direct_buffer_leak",
        "description": "Direct ByteBuffers not being released. Common with Netty network buffers and NIO operations.",
        "signs": ["io.netty.buffer.PoolDirectMemory", "java.nio.DirectByteBuffer", "DirectByteBuffer instances growing"],
        "check": "Check DirectByteBuffer count and total memory. Netty should release these but plugins may not.",
        "fix": "Ensure ByteBuf.release() is called in all code paths. Use ReferenceCountUtil.releaseLater() as safety net.",
    },
    {
        "pattern": "region_file_cache_leak",
        "description": "Minecraft RegionFile cache growing without eviction. Each loaded region keeps file handles and buffers.",
        "signs": ["net.minecraft.world.level.chunk.storage.RegionFile", "RegionFileStorage instances with many entries"],
        "check": "Count RegionFile instances. Should correlate with loaded chunks, not grow indefinitely.",
        "fix": "Reduce view-distance. Check paper-global.yml chunks.auto-save-interval. Ensure chunks are unloaded properly.",
    },
]

GC_LOG_LEAK_INDICATORS = [
    {
        "indicator": "old_gen_monotonic_growth",
        "description": "Old generation heap grows monotonically across GC cycles without significant reclaim",
        "how_to_check": "Run multiple 'jstat -gc <pid>' or check spark gc data. If old gen keeps growing after Full GC, it's a leak.",
        "positive_sign": "Old gen usage after Full GC: 80%+ and growing across 3+ consecutive cycles",
    },
    {
        "indicator": "full_gc_frees_little",
        "description": "Full GC runs but frees very little memory (less than 5% of old gen)",
        "how_to_check": "Compare old gen before and after Full GC. If <5% freed, objects are permanently reachable.",
        "positive_sign": "Full GC frees <5% of old gen. Old gen returns to nearly the same level quickly.",
    },
    {
        "indicator": "metaspace_growth",
        "description": "Metaspace (class metadata) growing continuously. Indicates classloader leaks or excessive dynamic class generation.",
        "how_to_check": "Run 'jstat -gcmetacapacity <pid>' or check spark heap data for metaspace growth.",
        "positive_sign": "Metaspace usage growing >10MB/hour without corresponding plugin loads.",
    },
    {
        "indicator": "allocation_rate_increase",
        "description": "Young gen filling faster over time, causing more frequent minor GCs. Indicates growing allocation rate from a leak.",
        "how_to_check": "Track young gen collection frequency over time. Increasing frequency = growing allocation rate.",
        "positive_sign": "Young GC frequency doubles over 1-2 hours while heap stays full.",
    },
]

QUICK_DIAGNOSTIC_COMMANDS = {
    "linux": {
        "jstat_gc": "jstat -gc <pid> 1000 10",
        "jstat_gcutil": "jstat -gcutil <pid> 1000 10",
        "jstat_gcnew": "jstat -gcnew <pid> 1000 10",
        "jstat_gcold": "jstat -gcold <pid> 1000 10",
        "jmap_heap": "jmap -heap <pid>",
        "jmap_histogram": "jmap -histo:live <pid> | head -50",
        "jmap_dump": "jmap -dump:format=b,file=heapdump.hprof <pid>",
        "jcmd_gc_class_histogram": "jcmd <pid> GC.class_histogram | head -50",
        "jcmd_gc_heap_info": "jcmd <pid> GC.heap_info",
        "jcmd_gc_run_finalization": "jcmd <pid> GC.run_finalization",
        "jcmd_thread_print": "jcmd <pid> Thread.print",
        "jcmd_vm_info": "jcmd <pid> VM.info",
        "jcmd_vm_native_memory": "jcmd <pid> VM.native_memory summary",
        "jcmd_vm_flag": "jcmd <pid> VM.flags",
        "find_java_pid": "ps aux | grep java | grep -v grep",
        "check_open_files": "ls /proc/<pid>/fd | wc -l",
        "check_fd_limit": "cat /proc/<pid>/limits | grep 'open files'",
        "check_process_memory": "cat /proc/<pid>/status | grep -E 'VmRSS|VmSize|VmPeak'",
        "check_direct_memory": "jcmd <pid> VM.native_memory | grep Internal",
    },
    "windows": {
        "jstat_gc": 'jstat -gc <pid> 1000 10',
        "jstat_gcutil": 'jstat -gcutil <pid> 1000 10',
        "jmap_heap": 'jmap -heap <pid>',
        "jmap_histogram": 'jmap -histo:live <pid> | more +0 | head -50',
        "jmap_dump": 'jmap -dump:format=b,file=heapdump.hprof <pid>',
        "jcmd_gc_class_histogram": 'jcmd <pid> GC.class_histogram | more +0 | head -50',
        "jcmd_gc_heap_info": 'jcmd <pid> GC.heap_info',
        "jcmd_thread_print": 'jcmd <pid> Thread.print',
        "jcmd_vm_info": 'jcmd <pid> VM.info',
        "jcmd_vm_flag": 'jcmd <pid> VM.flags',
        "find_java_pid": 'tasklist /FI "IMAGENAME eq java.exe"',
        "find_java_pid_wmic": 'wmic process where "name=\'java.exe\'" get ProcessId,CommandLine',
        "jvisualvm": 'jvisualvm',
    },
}


def detect_platform():
    if sys.platform == "win32":
        return "windows"
    return "linux"


def find_java_pid(platform):
    try:
        if platform == "linux":
            result = subprocess.run(["pgrep", "-f", "java"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                pids = result.stdout.strip().split("\n")
                return [p.strip() for p in pids if p.strip()]
        else:
            result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq java.exe", "/FO", "CSV", "/NH"],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                pids = []
                for line in result.stdout.strip().split("\n"):
                    parts = line.strip().strip('"').split('","')
                    if len(parts) >= 2:
                        pids.append(parts[1])
                return pids
    except Exception:
        pass
    return []


def parse_jmap_histogram(output_text):
    results = []
    for line in output_text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("num") or line.startswith("---"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            try:
                instances = int(parts[1])
                size_bytes = int(parts[2])
                class_name = " ".join(parts[3:])
                results.append({
                    "instances": instances,
                    "bytes": size_bytes,
                    "class_name": class_name,
                    "size_human": _format_bytes(size_bytes),
                })
            except (ValueError, IndexError):
                continue
    return results


def analyze_heap_histogram(entries, total_heap_bytes=None):
    if not entries:
        return {"error": "No histogram entries to analyze"}

    total_instances = sum(e["instances"] for e in entries)
    total_bytes = total_heap_bytes or sum(e["bytes"] for e in entries)

    findings = []
    type_breakdown = defaultdict(lambda: {"instances": 0, "bytes": 0})

    for entry in entries:
        cn = entry["class_name"]
        pct_bytes = (entry["bytes"] / total_bytes * 100) if total_bytes > 0 else 0
        pct_instances = (entry["instances"] / total_instances * 100) if total_instances > 0 else 0

        for pattern, info in MINECRAFT_LEAK_SIGNATURES.items():
            if pattern.lower() in cn.lower() or cn.lower().endswith(pattern.lower()):
                threshold = info.get("threshold_pct", info.get("threshold_instances", 0))
                triggered = False
                if "threshold_pct" in info and pct_bytes >= info["threshold_pct"]:
                    triggered = True
                elif "threshold_instances" in info and entry["instances"] >= info["threshold_instances"]:
                    triggered = True
                if triggered:
                    findings.append({
                        "severity": info["risk"],
                        "leak_type": info["leak_type"],
                        "class_name": cn,
                        "instances": entry["instances"],
                        "bytes": entry["bytes"],
                        "pct_of_heap": round(pct_bytes, 2),
                        "description": info["description"],
                        "threshold": f">{threshold}{'%' if 'threshold_pct' in info else ' instances'}",
                    })
                break

        category = _classify_entry(cn)
        type_breakdown[category]["instances"] += entry["instances"]
        type_breakdown[category]["bytes"] += entry["bytes"]

    string_pct = (type_breakdown.get("strings", {}).get("bytes", 0) / total_bytes * 100) if total_bytes > 0 else 0
    byte_array_pct = (type_breakdown.get("byte_arrays", {}).get("bytes", 0) / total_bytes * 100) if total_bytes > 0 else 0

    if string_pct > LEAK_PATTERN_THRESHOLDS["string_dominance_pct"]:
        findings.append({
            "severity": "WARNING",
            "leak_type": "string_dominance",
            "class_name": "java.lang.String + char[]",
            "instances": type_breakdown.get("strings", {}).get("instances", 0),
            "bytes": type_breakdown.get("strings", {}).get("bytes", 0),
            "pct_of_heap": round(string_pct, 2),
            "description": f"Strings and char[] consume {string_pct:.1f}% of heap. Enable -XX:+UseStringDeduplication with G1GC or ZGC.",
            "threshold": f">{LEAK_PATTERN_THRESHOLDS['string_dominance_pct']}%",
        })

    if byte_array_pct > LEAK_PATTERN_THRESHOLDS["byte_array_dominance_pct"]:
        findings.append({
            "severity": "WARNING",
            "leak_type": "byte_array_dominance",
            "class_name": "byte[]",
            "instances": type_breakdown.get("byte_arrays", {}).get("instances", 0),
            "bytes": type_breakdown.get("byte_arrays", {}).get("bytes", 0),
            "pct_of_heap": round(byte_array_pct, 2),
            "description": f"byte[] arrays consume {byte_array_pct:.1f}% of heap. Check packet buffers, NBT serialization, and plugin data.",
            "threshold": f">{LEAK_PATTERN_THRESHOLDS['byte_array_dominance_pct']}%",
        })

    findings.sort(key=lambda f: {"CRITICAL": 0, "HIGH": 1, "WARNING": 2, "MEDIUM": 3, "LOW": 4, "INFO": 5}.get(f.get("severity", "INFO"), 5))

    return {
        "total_heap_bytes": total_bytes,
        "total_heap_human": _format_bytes(total_bytes),
        "total_instances": total_instances,
        "type_breakdown": {k: {kk: (vv if kk != "bytes" else _format_bytes(vv)) for kk, vv in v.items()} for k, v in type_breakdown.items()},
        "top_consumers": entries[:20],
        "leak_findings": findings,
        "leak_patterns_checked": list(COMMON_LEAK_PATTERNS),
        "gc_log_indicators": GC_LOG_LEAK_INDICATORS,
    }


def _classify_entry(class_name):
    cn = class_name.lower()
    if cn.startswith("byte[") or cn == "byte[]":
        return "byte_arrays"
    if cn.startswith("char[") or cn == "char[]" or cn == "java.lang.string":
        return "strings"
    if cn.startswith("int[") or cn.startswith("long[") or cn.startswith("double[") or cn.startswith("float["):
        return "primitive_arrays"
    if cn.startswith("java.util.concurrent") or cn.startswith("java.util.hashmap") or cn.startswith("java.util.linkedhashmap") or cn.startswith("java.util.treemap"):
        return "collections"
    if cn.startswith("java.lang.thread") or cn.startswith("java.util.concurrent.threadpoolexecutor"):
        return "threads"
    if cn.startswith("io.netty"):
        return "netty"
    if cn.startswith("net.minecraft") or cn.startswith("org.bukkit") or cn.startswith("org.spigotmc") or cn.startswith("io.papermc"):
        return "minecraft_server"
    if "entity" in cn and ("minecraft" in cn or "bukkit" in cn):
        return "entities"
    if cn.startswith("java.lang.class") or cn.startswith("java.lang.reflect"):
        return "classloaders"
    return "other"


def _format_bytes(b):
    if b < 1024:
        return f"{b} B"
    if b < 1048576:
        return f"{b/1024:.1f} KB"
    if b < 1073741824:
        return f"{b/1048576:.1f} MB"
    return f"{b/1073741824:.2f} GB"


def cmd_analyze(args):
    platform = detect_platform()
    result = {"platform": platform}

    if args.hprof_file:
        hprof_info = parse_hprof_info(args.hprof_file)
        result["hprof_info"] = hprof_info
        if "error" not in hprof_info:
            result["hprof_file"] = args.hprof_file
            result["note"] = "HPROF file parsed successfully. For full histogram analysis, use 'jmap -histo:live <pid>' and pass the output with --jmap-histogram, or use Eclipse MAT to open the .hprof file directly."

    if args.jmap_histogram:
        with open(args.jmap_histogram, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        entries = parse_jmap_histogram(text)
        total = args.total_heap or None
        analysis = analyze_heap_histogram(entries, total)
        result.update(analysis)
        return result

    if args.pid:
        pid = args.pid
    else:
        pids = find_java_pid(platform)
        if len(pids) == 1:
            pid = pids[0]
            result["auto_detected_pid"] = pid
        elif len(pids) > 1:
            result["error"] = f"Multiple Java processes found: {pids}. Specify --pid."
            result["java_pids"] = pids
            return result
        else:
            result["error"] = "No Java process found. Is the Minecraft server running?"
            return result

    result["pid"] = pid
    jmap_path = shutil.which("jmap")
    jstat_path = shutil.which("jstat")
    jcmd_path = shutil.which("jcmd")

    if jmap_path:
        try:
            r = subprocess.run([jmap_path, "-histo:live", pid], capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                entries = parse_jmap_histogram(r.stdout)
                analysis = analyze_heap_histogram(entries)
                result["histogram_analysis"] = analysis
        except Exception as e:
            result["jmap_histogram_error"] = str(e)
    else:
        result["jmap_note"] = "jmap not found in PATH. Install JDK to use jmap -histo:live <pid>"

    if jstat_path:
        try:
            r = subprocess.run([jstat_path, "-gcutil", pid, "1000", "5"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                result["gc_utilization"] = r.stdout.strip()
        except Exception as e:
            result["jstat_error"] = str(e)

    if jcmd_path:
        try:
            r = subprocess.run([jcmd_path, pid, "GC.heap_info"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                result["heap_info"] = r.stdout.strip()
        except Exception as e:
            result["jcmd_error"] = str(e)

    result["diagnostic_commands"] = QUICK_DIAGNOSTIC_COMMANDS.get(platform, QUICK_DIAGNOSTIC_COMMANDS["linux"])

    return result


def cmd_commands(args):
    platform = detect_platform() if not args.windows else "windows" if args.windows else "linux"
    if args.windows:
        platform = "windows"
    elif args.linux:
        platform = "linux"

    return {
        "platform": platform,
        "diagnostic_commands": QUICK_DIAGNOSTIC_COMMANDS.get(platform, QUICK_DIAGNOSTIC_COMMANDS["linux"]),
        "leak_signatures": MINECRAFT_LEAK_SIGNATURES,
        "common_leak_patterns": COMMON_LEAK_PATTERNS,
        "gc_log_indicators": GC_LOG_LEAK_INDICATORS,
    }


def cmd_leak_check(args):
    platform = detect_platform()
    result = {
        "platform": platform,
        "leak_signatures": MINECRAFT_LEAK_SIGNATURES,
        "common_leak_patterns": COMMON_LEAK_PATTERNS,
        "gc_log_indicators": GC_LOG_LEAK_INDICATORS,
        "diagnostic_commands": QUICK_DIAGNOSTIC_COMMANDS.get(platform, QUICK_DIAGNOSTIC_COMMANDS["linux"]),
    }

    if args.hprof_file:
        hprof_info = parse_hprof_info(args.hprof_file)
        result["hprof_info"] = hprof_info

    if args.jmap_histogram:
        with open(args.jmap_histogram, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        entries = parse_jmap_histogram(text)
        total = args.total_heap or None
        analysis = analyze_heap_histogram(entries, total)
        result["histogram_analysis"] = analysis

    return result


def build_parser():
    parser = argparse.ArgumentParser(
        prog="heapdump_analyzer",
        description="Heap Dump Analyzer for Minecraft Servers - detect memory leaks and usage patterns",
    )
    sub = parser.add_subparsers(dest="command", help="Analysis command")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--pid", "-p", help="Java process ID (auto-detected if not specified)")
    common.add_argument("--jmap-histogram", help="Path to jmap -histo:live output file to analyze")
    common.add_argument("--total-heap", type=int, help="Total heap size in bytes (for percentage calculations)")
    common.add_argument("--output", "-o", help="Write output to file instead of stdout")
    common.add_argument("--indent", type=int, default=2, help="JSON indent (default: 2, 0 for compact)")

    analyze_p = sub.add_parser("analyze", parents=[common], help="Analyze heap histogram for leaks and bloat")
    analyze_p.add_argument("--hprof-file", help="Path to .hprof heap dump file for header info (full parsing requires Eclipse MAT)")
    commands_p = sub.add_parser("commands", parents=[common], help="Show diagnostic commands for the current platform")
    commands_p.add_argument("--windows", action="store_true", help="Show Windows commands")
    commands_p.add_argument("--linux", action="store_true", help="Show Linux commands")
    leak_check_p = sub.add_parser("leak-check", parents=[common], help="Check histogram data against known Minecraft leak patterns")
    leak_check_p.add_argument("--hprof-file", help="Path to .hprof heap dump file for header info")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "analyze": cmd_analyze,
        "commands": cmd_commands,
        "leak-check": cmd_leak_check,
    }

    handler = commands.get(args.command)
    if not handler:
        print(f"Unknown command: {args.command}")
        sys.exit(1)

    try:
        result = handler(args)
    except Exception as e:
        result = {"error": f"Unexpected error: {type(e).__name__}: {e}"}

    indent = args.indent if args.indent > 0 else None
    output = json.dumps(result, indent=indent, default=str, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Output written to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()