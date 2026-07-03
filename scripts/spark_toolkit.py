#!/usr/bin/env python3
"""
Lucko Spark Profile Analyzer Toolkit

Comprehensive CLI tool for fetching, parsing, filtering, and analyzing
Lucko Spark profiler data from spark.lucko.me URLs and local files.

Designed as an AI-first utility: all output is structured JSON for easy
parsing by agents. Every command supports filtering to target specific
threads, plugins, classes, methods, and time windows.

Usage:
    python3 spark_toolkit.py <command> [options]

Commands:
    fetch       Fetch profile data from spark.lucko.me URL
    info        Extract platform/metadata summary
    threads     List and analyze threads
    tree        Dump profiler tree with filtering
    hotspots    Find top hotspots across threads
    plugins     Attribute time to plugins/mods (sources view)
    tps         Extract TPS/MSPT data
    gc          Extract GC statistics
    health      Parse health report window data
    heap        Parse heap summary data
    entities    Extract entity/world statistics
    search      Search stack trace nodes by class/method pattern
    callpath    Trace call path to a specific method
    compare     Compare two time windows
    report      Generate full analysis report
    analyze-gc  Deep GC analysis with ZGC/G1GC insights and tuning
    analyze-tps TPS/MSPT analysis with lag spike detection
    analyze-cpu CPU usage analysis with thread attribution
    recommend   Comprehensive performance recommendations
    check-config Analyze JVM flags and server config files
    pipeline   Analyze netty pipeline handler chain
    plugin-heap Heap usage attributed to a specific plugin
    plugin-profile Complete plugin performance profile

Run 'python3 spark_toolkit.py <command> --help' for command-specific options.

Dependencies:
    protobuf    Required for parsing .sparkprofile binary files.
                Install: pip install protobuf  (or pip3 install protobuf)
"""

import argparse
import gzip
import json
import math
import os
import re
import sys
import time
import urllib.request
import urllib.error
import warnings
from collections import defaultdict
from pathlib import Path

_PROTO_LOADED = False
spark_pb2 = None


def _ensure_proto():
    global _PROTO_LOADED, spark_pb2
    if _PROTO_LOADED:
        return spark_pb2 is not None
    _PROTO_LOADED = True
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        proto_dir = os.path.join(os.path.dirname(script_dir), "proto")
        if proto_dir not in sys.path:
            sys.path.insert(0, proto_dir)
        import spark_pb2 as _spark_pb2
        spark_pb2 = _spark_pb2
        return True
    except Exception:
        spark_pb2 = None
        return False

SPARK_VIEWER_BASE = "https://spark.lucko.me"
SPARK_RAW_BASE = "https://spark-usercontent.lucko.me"

PROTO_TYPE_MAP = {0: "SERVER", 1: "CLIENT", 2: "PROXY", 3: "APPLICATION"}
SAMPLER_MODE_MAP = {0: "EXECUTION", 1: "ALLOCATION"}
SAMPLER_ENGINE_MAP = {0: "JAVA", 1: "ASYNC"}
AGGREGATOR_TYPE_MAP = {0: "SIMPLE", 1: "TICKED"}
THREAD_GROUPER_MAP = {0: "BY_NAME", 1: "BY_POOL", 2: "AS_ONE"}


def _proto_node_to_dict(node, flat_children, visited=None):
    if visited is None:
        visited = set()
    node_id = id(node)
    if node_id in visited:
        return {"className": node.class_name, "methodName": node.method_name, "times": list(node.times), "children": []}
    visited.add(node_id)

    d = {
        "className": node.class_name,
        "methodName": node.method_name,
        "times": list(node.times),
    }
    if node.line_number:
        d["lineNumber"] = node.line_number
    if node.method_desc:
        d["methodDesc"] = node.method_desc

    children = []
    for ref in node.children_refs:
        if 0 <= ref < len(flat_children):
            child_node = flat_children[ref]
            children.append(_proto_node_to_dict(child_node, flat_children, visited))
    d["children"] = children
    return d


def _proto_thread_to_dict(thread_node):
    flat_children = list(thread_node.children)
    if thread_node.children_refs:
        root_indices = list(thread_node.children_refs)
    else:
        root_indices = list(range(len(flat_children)))

    visited = set()
    root_children = []
    for idx in root_indices:
        if 0 <= idx < len(flat_children):
            root_children.append(_proto_node_to_dict(flat_children[idx], flat_children, visited))

    return {
        "name": thread_node.name,
        "times": list(thread_node.times),
        "children": root_children,
    }


def _proto_gc_to_dict(gc_msg):
    freq_ms = gc_msg.avg_frequency
    freq_per_min = round(60000.0 / freq_ms, 2) if freq_ms > 0 else 0
    return {
        "total": gc_msg.total,
        "avgTime": gc_msg.avg_time,
        "avgFrequency": freq_per_min,
    }


def _proto_rolling_avg_to_dict(ra):
    if not ra.mean and not ra.max and not ra.median:
        return {}
    return {
        "mean": ra.mean,
        "max": ra.max,
        "min": ra.min,
        "median": ra.median,
        "percentile95": ra.percentile95,
    }


def _proto_memory_usage_to_dict(mu):
    return {
        "used": mu.used,
        "committed": mu.committed,
        "max": mu.max,
    }


def _proto_platform_stats_to_dict(ps):
    d = {}
    if ps.HasField("memory"):
        mem = {}
        if ps.memory.HasField("heap"):
            mem["heap"] = _proto_memory_usage_to_dict(ps.memory.heap)
        if ps.memory.HasField("non_heap"):
            mem["nonHeap"] = _proto_memory_usage_to_dict(ps.memory.non_heap)
        if ps.memory.pools:
            mem["pools"] = []
            for pool in ps.memory.pools:
                pool_d = {"name": pool.name}
                if pool.HasField("before"):
                    pool_d["before"] = _proto_memory_usage_to_dict(pool.before)
                if pool.HasField("after"):
                    pool_d["after"] = _proto_memory_usage_to_dict(pool.after)
                mem["pools"].append(pool_d)
        d["memory"] = mem
    gc_map = {}
    for name in ps.gc:
        gc_map[name] = _proto_gc_to_dict(ps.gc[name])
    if gc_map:
        d["gc"] = gc_map
    d["uptime"] = ps.uptime
    if ps.HasField("tps"):
        d["tps"] = {
            "last1m": ps.tps.last1m,
            "last5m": ps.tps.last5m,
            "last15m": ps.tps.last15m,
            "gameTargetTps": ps.tps.game_target_tps if ps.tps.game_target_tps else 20,
        }
    if ps.HasField("mspt"):
        mspt_d = {}
        if ps.mspt.HasField("last1m"):
            mspt_d["last1m"] = _proto_rolling_avg_to_dict(ps.mspt.last1m)
        if ps.mspt.HasField("last5m"):
            mspt_d["last5m"] = _proto_rolling_avg_to_dict(ps.mspt.last5m)
        mspt_d["gameMaxIdealMspt"] = ps.mspt.game_max_ideal_mspt
        d["mspt"] = mspt_d
    if ps.HasField("ping"):
        d["ping"] = {
            "last1m": ps.ping.last1m,
            "last5m": ps.ping.last5m,
            "last15m": ps.ping.last15m,
        }
    d["playerCount"] = ps.player_count
    if ps.HasField("world"):
        w = ps.world
        world_d = {
            "totalEntities": w.total_entities,
            "entityCounts": dict(w.entity_counts),
            "worlds": [],
        }
        for wo in w.worlds:
            wo_d = {"name": wo.name, "totalEntities": wo.total_entities, "regions": []}
            for r in wo.regions:
                r_d = {"totalEntities": r.total_entities, "chunks": []}
                for c in r.chunks:
                    r_d["chunks"].append({
                        "x": c.x, "z": c.z,
                        "totalEntities": c.total_entities,
                        "entityCounts": dict(c.entity_counts),
                    })
                wo_d["regions"].append(r_d)
            world_d["worlds"].append(wo_d)
        d["world"] = world_d
    if ps.HasField("online_mode"):
        d["onlineMode"] = ps.online_mode.online
    return d


def _proto_system_stats_to_dict(ss):
    d = {}
    if ss.HasField("cpu"):
        cpu = ss.cpu
        cpu_d = {
            "threads": cpu.threads,
            "modelName": cpu.model_name,
        }
        if cpu.HasField("process_usage"):
            cpu_d["processUsage"] = {"last1m": cpu.process_usage.last1m, "last15m": cpu.process_usage.last15m}
        if cpu.HasField("system_usage"):
            cpu_d["systemUsage"] = {"last1m": cpu.system_usage.last1m, "last15m": cpu.system_usage.last15m}
        d["cpu"] = cpu_d
    if ss.HasField("memory"):
        mem = ss.memory
        mem_d = {}
        if mem.HasField("physical"):
            mem_d["physical"] = {"used": mem.physical.used, "total": mem.physical.total}
        if mem.HasField("swap"):
            mem_d["swap"] = {"used": mem.swap.used, "total": mem.swap.total}
        d["memory"] = mem_d
    gc_map = {}
    for name in ss.gc:
        gc_map[name] = _proto_gc_to_dict(ss.gc[name])
    if gc_map:
        d["gc"] = gc_map
    if ss.HasField("disk"):
        d["disk"] = {"total": ss.disk.total, "free": ss.disk.free}
    if ss.HasField("os"):
        d["os"] = {"name": ss.os.name, "arch": ss.os.arch, "version": ss.os.version}
    if ss.HasField("java"):
        d["java"] = {"version": ss.java.version, "vendor": ss.java.vendor}
        if ss.java.runtime_name:
            d["java"]["runtimeName"] = ss.java.runtime_name
        if ss.java.flags:
            d["jvm_flags"] = ss.java.flags
    d["uptime"] = ss.uptime
    if ss.HasField("jvm"):
        d["jvm"] = {"name": ss.jvm.name, "version": ss.jvm.version, "vendor": ss.jvm.vendor}
    return d


def _proto_window_stats_to_dict(ws):
    return {
        "ticks": ws.ticks,
        "cpu_process": ws.cpu_process,
        "cpu_system": ws.cpu_system,
        "tps": ws.tps,
        "mspt_median": ws.mspt_median,
        "mspt_max": ws.mspt_max,
        "players": ws.players,
        "entities": ws.entities,
        "tile_entities": ws.tile_entities,
        "chunks": ws.chunks,
        "start_time": ws.start_time,
        "end_time": ws.end_time,
        "duration": ws.duration,
    }


def parse_protobuf_sampler(data_bytes):
    if not _ensure_proto():
        return None
    sampler = spark_pb2.SamplerData()
    sampler.ParseFromString(data_bytes)
    meta = sampler.metadata
    pm = meta.platform_metadata

    sources = {}
    for key in meta.sources:
        s = meta.sources[key]
        sources[key] = {
            "name": s.name,
            "version": s.version,
            "author": s.author,
            "description": s.description,
        }

    data_aggregator = meta.data_aggregator

    result = {
        "type": "sampler",
        "metadata": {
            "platformMetadata": {
                "type": PROTO_TYPE_MAP.get(pm.type, pm.type),
                "name": pm.name,
                "version": pm.version,
                "minecraftVersion": pm.minecraft_version,
                "sparkVersion": pm.spark_version,
                "brand": pm.brand,
            },
            "interval": meta.interval,
            "startTime": meta.start_time,
            "endTime": meta.end_time,
            "numberOfTicks": meta.number_of_ticks,
            "samplerMode": SAMPLER_MODE_MAP.get(meta.sampler_mode, meta.sampler_mode),
            "samplerEngine": SAMPLER_ENGINE_MAP.get(meta.sampler_engine, meta.sampler_engine),
            "samplerEngineVersion": meta.sampler_engine_version,
            "dataAggregator": {
                "type": AGGREGATOR_TYPE_MAP.get(data_aggregator.type, data_aggregator.type),
                "threadGrouper": THREAD_GROUPER_MAP.get(data_aggregator.thread_grouper, data_aggregator.thread_grouper),
                "tickLengthThreshold": data_aggregator.tick_length_threshold,
                "numberOfIncludedTicks": data_aggregator.number_of_included_ticks,
            },
            "serverConfigurations": dict(meta.server_configurations),
            "sources": sources,
            "comment": meta.comment,
        },
        "threads": [_proto_thread_to_dict(t) for t in sampler.threads],
        "classSources": dict(sampler.class_sources),
        "methodSources": dict(sampler.method_sources),
        "lineSources": dict(sampler.line_sources),
        "timeWindows": list(sampler.time_windows),
    }

    if sampler.HasField("metadata"):
        if meta.HasField("platform_statistics"):
            result["metadata"]["platformStatistics"] = _proto_platform_stats_to_dict(meta.platform_statistics)
        if meta.HasField("system_statistics"):
            result["metadata"]["systemStatistics"] = _proto_system_stats_to_dict(meta.system_statistics)

    ws = {}
    for key in sampler.time_window_statistics:
        ws[str(key)] = _proto_window_stats_to_dict(sampler.time_window_statistics[key])
    if ws:
        result["timeWindowStatistics"] = ws

    return result


def parse_protobuf_heap(data_bytes):
    if not _ensure_proto():
        return None
    heap = spark_pb2.HeapData()
    heap.ParseFromString(data_bytes)
    meta = heap.metadata
    pm = meta.platform_metadata

    result = {
        "type": "heap",
        "metadata": {
            "platformMetadata": {
                "type": PROTO_TYPE_MAP.get(pm.type, pm.type),
                "name": pm.name,
                "version": pm.version,
                "minecraftVersion": pm.minecraft_version,
                "sparkVersion": pm.spark_version,
                "brand": pm.brand,
            },
        },
        "entries": [],
    }

    if meta.HasField("platform_statistics"):
        result["metadata"]["platformStatistics"] = _proto_platform_stats_to_dict(meta.platform_statistics)
    if meta.HasField("system_statistics"):
        result["metadata"]["systemStatistics"] = _proto_system_stats_to_dict(meta.system_statistics)

    sources = {}
    for key in meta.sources:
        s = meta.sources[key]
        sources[key] = {"name": s.name, "version": s.version, "author": s.author, "description": s.description}
    if sources:
        result["metadata"]["sources"] = sources

    for entry in heap.entries:
        result["entries"].append({
            "order": entry.order,
            "instances": entry.instances,
            "size": entry.size,
            "type": entry.type,
        })

    return result


def parse_protobuf_health(data_bytes):
    if not _ensure_proto():
        return None
    health = spark_pb2.HealthData()
    health.ParseFromString(data_bytes)
    meta = health.metadata
    pm = meta.platform_metadata

    result = {
        "type": "health",
        "metadata": {
            "platformMetadata": {
                "type": PROTO_TYPE_MAP.get(pm.type, pm.type),
                "name": pm.name,
                "version": pm.version,
                "minecraftVersion": pm.minecraft_version,
                "sparkVersion": pm.spark_version,
                "brand": pm.brand,
            },
        },
    }

    if meta.HasField("system_statistics"):
        result["metadata"]["systemStatistics"] = _proto_system_stats_to_dict(meta.system_statistics)

    ws = {}
    for key in health.time_window_statistics:
        ws[str(key)] = _proto_window_stats_to_dict(health.time_window_statistics[key])
    if ws:
        result["timeWindowStatistics"] = ws

    return result


def parse_protobuf_file(path):
    with open(path, "rb") as f:
        data_bytes = f.read()

    last_error = None
    for parser in [parse_protobuf_sampler, parse_protobuf_heap, parse_protobuf_health]:
        try:
            result = parser(data_bytes)
            if result:
                return result
        except Exception as e:
            last_error = e
            continue
    if last_error is not None:
        # Surface the real parse failure instead of a generic "install protobuf" hint,
        # which is misleading when protobuf IS installed but the data is corrupt/mismatched.
        warnings.warn(f"parse_protobuf_file: all parsers failed for {path}; last error: {type(last_error).__name__}: {last_error}")
    return None


def extract_id(url_or_id):
    s = url_or_id.strip().rstrip("/")
    if "/" in s:
        return s.rsplit("/", 1)[-1].split("?")[0].split("#")[0]
    return s.split("?")[0].split("#")[0]


def fetch_json(profile_id, full=False, path=None):
    url = f"{SPARK_VIEWER_BASE}/{profile_id}?raw=1"
    if full:
        url += "&full=true"
    if path:
        url += f"&path={path}"
    req = urllib.request.Request(url, headers={"User-Agent": "spark-toolkit/2.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_raw(profile_id):
    url = f"{SPARK_RAW_BASE}/{profile_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "spark-toolkit/2.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        ct = resp.headers.get("Content-Type", "")
        data = resp.read()
        if "sampler" in ct:
            ptype = "sampler"
        elif "heap" in ct:
            ptype = "heap"
        elif "health" in ct:
            ptype = "health"
        else:
            ptype = "unknown"
        return data, ptype, ct


def open_file(path):
    p = str(path).lower()
    if p.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def _is_likely_protobuf(file_path):
    with open(file_path, "rb") as f:
        header = f.read(8)
    if len(header) < 2:
        return False
    first_byte = header[0]
    json_starters = {0x7b, 0x5b, 0x22, 0x09, 0x0a, 0x0d, 0x20}
    if first_byte in json_starters:
        return False
    if first_byte == 0x7d:
        return False
    try:
        with open(file_path, "r", encoding="utf-8", errors="strict") as f:
            f.read(4096)
        return False
    except (UnicodeDecodeError, UnicodeError):
        return True


SLEEP_METHODS = {
    "waitfornexttick", "thread.sleep", "locksupport.park", "object.wait",
    "unsafe.park", "park", "parknanos", "parkuntil",
}

NATIVE_IDLE_METHODS = {
    "pthread_cond_wait", "pthread_cond_timedwait", "pthread_cond_signal",
    "pthread_mutex_lock", "pthread_mutex_unlock",
    "epoll_wait", "epoll_pwait", "epoll_pwait2",
    "waituntildeadline", "waitfortick",
    "futex_wait", "futex_wake",
    "__nanosleep", "__poll", "__select", "__accept",
    "socketaccept",
    "native_epoll_wait",
}

FOLIA_CANVAS_IDLE_PATTERNS = [
    "affinityschedulerthreadpool$tickthreadrunner.waituntildeadline",
    "affinityschedulerthreadpool$tickthreadrunner.waitfortick",
    "tickregionScheduler$regionizedtaskqueue$regionqueue.scheduledinternal",
    "regionizedtaskqueue",
    "regionscheduler$regionschedulehandle",
]


def _is_idle_frame(class_name, method_name):
    cn = (class_name or "").lower()
    mn = (method_name or "").lower()
    for s in SLEEP_METHODS:
        if s in mn:
            return True
    for s in NATIVE_IDLE_METHODS:
        if s in mn or s in cn:
            return True
    for pattern in FOLIA_CANVAS_IDLE_PATTERNS:
        if pattern in cn or pattern in mn or pattern in (cn + "." + mn):
            return True
    return False


def _is_folia_region_thread(thread_name):
    n = thread_name.lower()
    return "region" in n or "folia" in n or "canvas" in n or "tickthreadrunner" in n


def _detect_jdk_version(sstats, meta):
    java_info = sstats.get("java", {})
    jvm_info = sstats.get("jvm", {})
    jvm_version = java_info.get("version", jvm_info.get("version", ""))
    flags_str = ""
    configs = meta.get("serverConfigurations", meta.get("server_configurations", {}))
    if configs:
        flags_str = configs.get("jvm_args", configs.get("flags", ""))
    if not flags_str:
        flags_str = sstats.get("jvm_flags", "")
    if not flags_str:
        flags_str = java_info.get("flags", "")
    return {"version": jvm_version, "flags": flags_str}


def load_data(source):
    if source.startswith("http://") or source.startswith("https://"):
        pid = extract_id(source)
        try:
            return fetch_json(pid, full=True), "json_url"
        except Exception as e:
            print(f"spark_toolkit: fetch failed for {source}: {type(e).__name__}: {e}", file=sys.stderr)
            return None, None
    if re.match(r'^[a-zA-Z0-9]{4,20}$', source):
        try:
            return fetch_json(source, full=True), "json_url"
        except Exception as e:
            print(f"spark_toolkit: fetch failed for profile {source}: {type(e).__name__}: {e}", file=sys.stderr)
            return None, None
    if os.path.isfile(source):
        with open(source, "rb") as f:
            header = f.read(8)
        is_protobuf = _is_likely_protobuf(source)
        p = str(source).lower()
        is_sparkprofile = p.endswith(".sparkprofile") or p.endswith(".sparkprofile.gz")
        if is_protobuf or is_sparkprofile or header[0] not in (0x7b, 0x5b, 0x7d, 0x22, 0x09, 0x0a, 0x0d, 0x20):
            proto_result = parse_protobuf_file(source)
            if proto_result:
                return proto_result, "file_protobuf"
            if is_protobuf or is_sparkprofile:
                if _ensure_proto():
                    msg = "Failed to parse protobuf file. The 'protobuf' package is installed, but all parsers (sampler/heap/health) rejected the data -- the file may be corrupt or use an incompatible schema version."
                else:
                    msg = "Failed to parse protobuf file. The 'protobuf' package is not installed: pip install protobuf"
                return {"error": msg, "file": source}, "file_protobuf_error"
        if p.endswith(".gz"):
            with gzip.open(source, "rt", encoding="utf-8", errors="replace") as f:
                content = f.read()
        else:
            with open(source, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        try:
            data = json.loads(content)
            return data, "file_json"
        except json.JSONDecodeError:
            proto_result = parse_protobuf_file(source)
            if proto_result:
                return proto_result, "file_protobuf"
            return {"_raw_file": source, "_format": "unparseable"}, "file_raw"
    try:
        return json.loads(source), "inline_json"
    except (json.JSONDecodeError, TypeError):
        return None, None


def get_metadata(data):
    return data.get("metadata", data)


def get_profile_type(data):
    return data.get("type", "unknown")


def get_platform_meta(meta):
    pm = meta.get("platformMetadata", meta.get("platform", {}))
    type_map = {0: "SERVER", 1: "CLIENT", 2: "PROXY", 3: "APPLICATION"}
    raw_type = pm.get("type", 0)
    ptype = type_map.get(raw_type, "UNKNOWN") if isinstance(raw_type, int) else raw_type
    result = {
        "type": ptype,
        "name": pm.get("name", "unknown"),
        "version": pm.get("version", "unknown"),
        "minecraft_version": pm.get("minecraftVersion", pm.get("minecraft_version", "unknown")),
        "spark_version": pm.get("sparkVersion", pm.get("spark_version", 0)),
        "brand": pm.get("brand", ""),
    }
    return result


def get_platform_stats(meta):
    return meta.get("platformStatistics", meta.get("platform_statistics", {}))


def get_system_stats(meta):
    return meta.get("systemStatistics", meta.get("system_statistics", {}))


def get_threads(data):
    return data.get("threads", [])


def get_class_sources(data):
    return data.get("classSources", data.get("class_sources", {}))


def get_method_sources(data):
    return data.get("methodSources", data.get("method_sources", {}))


def get_line_sources(data):
    return data.get("lineSources", data.get("line_sources", {}))


def get_sources(meta):
    return meta.get("sources", {})


def get_time_windows(data):
    return data.get("timeWindows", data.get("time_windows", []))


def get_window_stats(data):
    return data.get("timeWindowStatistics", data.get("time_window_statistics", {}))


def pct(part, whole):
    if whole == 0:
        return 0.0
    return round(part / whole * 100, 2)


def format_bytes(b):
    if b < 1024:
        return f"{b} B"
    if b < 1048576:
        return f"{b/1024:.1f} KB"
    if b < 1073741824:
        return f"{b/1048576:.1f} MB"
    return f"{b/1073741824:.2f} GB"


def assess_tps(tps_val):
    if tps_val >= 19.5:
        return "GOOD"
    if tps_val >= 15:
        return "WARNING"
    return "CRITICAL"


def assess_mspt(mspt_val):
    if mspt_val <= 30:
        return "GOOD"
    if mspt_val <= 45:
        return "WARNING"
    return "CRITICAL"


def thread_matches(thread_name, filters):
    if not filters:
        return True
    name_lower = thread_name.lower()
    for f in filters:
        f_lower = f.lower()
        if f_lower == "server" and ("server" in name_lower or "main" in name_lower):
            return True
        if f_lower == "netty" and "netty" in name_lower:
            return True
        if f_lower == "region" and "region" in name_lower:
            return True
        if f_lower in name_lower:
            return True
    return False


def node_matches_class(node, pattern):
    if not pattern:
        return True
    cn = node.get("className", node.get("class_name", ""))
    mn = node.get("methodName", node.get("method_name", ""))
    full = f"{cn}.{mn}"
    p = pattern.lower()
    return p in full.lower() or bool(re.search(pattern, full, re.IGNORECASE))


def walk_tree(node, depth=0, total_time=None, min_pct=0.0, max_depth=100, class_filter=None, path=None):
    if path is None:
        path = []
    if depth > max_depth:
        return []

    cn = node.get("className", node.get("class_name", ""))
    mn = node.get("methodName", node.get("method_name", ""))
    times = node.get("times", [])
    total = sum(times) if times else 0

    sig = f"{cn}.{mn}"
    current_path = path + [sig]

    pct_val = pct(total, total_time) if total_time else 0
    if min_pct > 0 and pct_val < min_pct and depth > 0:
        return []

    result = {
        "class": cn,
        "method": mn,
        "line": node.get("lineNumber", node.get("line_number")),
        "time_total": total,
        "time_pct": pct_val,
        "depth": depth,
        "path": " -> ".join(current_path),
    }

    entries = [result]
    children = node.get("children", [])
    if not children:
        children_refs = node.get("childrenRefs", node.get("children_refs", []))
    for child in children:
        if class_filter and not node_matches_class(child, class_filter):
            filtered_children = walk_tree(child, depth + 1, total_time, min_pct, max_depth, class_filter, current_path)
            if filtered_children:
                entries.extend(filtered_children)
            continue
        entries.extend(walk_tree(child, depth + 1, total_time, min_pct, max_depth, class_filter, current_path))

    return entries


def find_hotspots(node, total_time, min_pct=1.0, path=None):
    if path is None:
        path = []
    cn = node.get("className", node.get("class_name", ""))
    mn = node.get("methodName", node.get("method_name", ""))
    times = node.get("times", [])
    total = sum(times) if times else 0
    self_time = total - sum(sum(c.get("times", [])) for c in node.get("children", []))
    sig = f"{cn}.{mn}"
    current_path = path + [sig]

    results = []
    pct_val = pct(total, total_time) if total_time else 0
    self_pct = pct(self_time, total_time) if total_time else 0

    if self_pct >= min_pct:
        results.append({
            "class": cn,
            "method": mn,
            "self_time": self_time,
            "total_time": total,
            "self_pct": self_pct,
            "total_pct": pct_val,
            "path": " -> ".join(current_path),
        })

    for child in node.get("children", []):
        results.extend(find_hotspots(child, total_time, min_pct, current_path))

    return results


def attribute_to_source(node, class_sources, method_sources, sources_meta, path=None):
    if path is None:
        path = []
    cn = node.get("className", node.get("class_name", ""))
    mn = node.get("methodName", node.get("method_name", ""))
    times = node.get("times", [])
    total = sum(times) if times else 0
    sig = f"{cn}.{mn}"
    current_path = path + [sig]

    source = class_sources.get(cn) or method_sources.get(sig) or "Unknown"
    for name, info in sources_meta.items():
        pkg = info.get("name", name).lower()
        if pkg and pkg in cn.lower():
            source = info.get("name", name)
            break

    results = [{source: total}]

    for child in node.get("children", []):
        child_attrs = attribute_to_source(child, class_sources, method_sources, sources_meta, current_path)
        for d in child_attrs:
            for k, v in d.items():
                results.append({k: v})

    merged = defaultdict(float)
    for d in results:
        for k, v in d.items():
            merged[k] += v

    return [dict({k: v}) for k, v in merged.items()]


def cmd_fetch(args):
    pid = extract_id(args.source)
    output = {"profile_id": pid}

    try:
        meta_only = fetch_json(pid, full=False)
        output["metadata_available"] = True
        output["profile_type"] = meta_only.get("type", "unknown")
        meta = get_metadata(meta_only)
        output["platform"] = get_platform_meta(meta)
    except Exception as e:
        output["metadata_error"] = str(e)
        output["metadata_available"] = False

    if args.full:
        try:
            full_data = fetch_json(pid, full=True)
            output["full_data"] = full_data
        except Exception as e:
            output["full_data_error"] = str(e)

    try:
        raw_data, ptype, ct = fetch_raw(pid)
        output["raw_data"] = {
            "available": True,
            "type": ptype,
            "content_type": ct,
            "size_bytes": len(raw_data),
            "size_human": format_bytes(len(raw_data)),
        }
    except Exception as e:
        output["raw_data"] = {"available": False, "error": str(e)}

    return output


def cmd_info(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    meta = get_metadata(data)
    ptype = get_profile_type(data)
    platform = get_platform_meta(meta)
    pstats = get_platform_stats(meta)
    sstats = get_system_stats(meta)
    sources = get_sources(meta)

    result = {
        "source_type": src,
        "profile_type": ptype,
        "platform": platform,
    }

    if pstats:
        tps = pstats.get("tps", {})
        mspt = pstats.get("mspt", {})
        if tps:
            result["tps"] = {
                "1m": {"value": tps.get("last1m"), "status": assess_tps(tps.get("last1m", 0))},
                "5m": {"value": tps.get("last5m"), "status": assess_tps(tps.get("last5m", 0))},
                "15m": {"value": tps.get("last15m"), "status": assess_tps(tps.get("last15m", 0))},
                "target": tps.get("gameTargetTps", tps.get("game_target_tps", 20)),
            }
        if mspt:
            m1 = mspt.get("last1m", {})
            m5 = mspt.get("last5m", {})
            result["mspt"] = {
                "1m": {
                    "mean": m1.get("mean"), "median": m1.get("median"),
                    "p95": m1.get("percentile95"), "max": m1.get("max"), "min": m1.get("min"),
                },
                "5m": {
                    "mean": m5.get("mean"), "median": m5.get("median"),
                    "p95": m5.get("percentile95"), "max": m5.get("max"), "min": m5.get("min"),
                },
                "ideal_mspt": mspt.get("gameMaxIdealMspt", mspt.get("game_max_ideal_mspt", 50)),
            }

    if sstats:
        cpu = sstats.get("cpu", {})
        result["system"] = {
            "cpu_model": cpu.get("modelName", cpu.get("model_name", "unknown")),
            "cpu_threads": cpu.get("threads", 0),
            "cpu_process_1m": cpu.get("processUsage", cpu.get("process_usage", {})).get("last1m"),
            "cpu_system_1m": cpu.get("systemUsage", cpu.get("system_usage", {})).get("last1m"),
        }
        mem = sstats.get("memory", {})
        if mem:
            phys = mem.get("physical", {})
            result["system"]["memory_physical_used"] = phys.get("used")
            result["system"]["memory_physical_total"] = phys.get("total")
        java = sstats.get("java", {})
        if java:
            result["system"]["java_version"] = java.get("version", "unknown")
            result["system"]["java_vendor"] = java.get("vendor", "unknown")
        jvm = sstats.get("jvm", {})
        if jvm:
            result["system"]["jvm_name"] = jvm.get("name", "unknown")
            result["system"]["jvm_version"] = jvm.get("version", "unknown")
            if jvm.get("vendor"):
                result["system"]["jvm_vendor"] = jvm["vendor"]

        jdk_info = _detect_jdk_version(sstats, meta)
        jdk_version = jdk_info.get("version", "")
        jdk_major = 0
        if jdk_version:
            try:
                parts = jdk_version.split(".")
                if parts[0] == "1" and len(parts) > 1:
                    jdk_major = int(parts[1])
                else:
                    jdk_major = int(parts[0])
            except (ValueError, IndexError):
                pass
        jdk_notes = []
        if jdk_major >= 25:
            jdk_notes.append("JDK 25+: UseCompactObjectHeaders is available for reduced memory overhead")
            jdk_notes.append("JDK 25+: ZGenerational (Generational ZGC) is production-ready and recommended over single-generation ZGC")
            jdk_notes.append("JDK 25+: Compact Object Headers may cause issues with some native libraries - test thoroughly")
        elif jdk_major >= 21:
            jdk_notes.append("JDK 21+: ZGenerational (Generational ZGC) is available with -XX:+ZGenerational")
            jdk_notes.append("JDK 21+: Virtual threads available but not recommended for Minecraft main tick loop")
        elif jdk_major >= 17:
            jdk_notes.append("JDK 17: Good baseline for Minecraft servers. Consider upgrading to JDK 21 for ZGenerational ZGC.")
        elif jdk_major < 17 and jdk_major > 0:
            jdk_notes.append(f"JDK {jdk_major}: Below JDK 17. Strongly recommend upgrading to JDK 21 for performance and security.")
        if jdk_notes:
            result["jdk_awareness"] = {"version": jdk_version, "major": jdk_major, "notes": jdk_notes}

    configs = meta.get("serverConfigurations", meta.get("server_configurations", {}))
    if configs:
        result["jvm_flags"] = configs.get("jvm_args", configs.get("flags", ""))

    if sstats and not result.get("jvm_flags"):
        jvm_flags = sstats.get("jvm_flags", "")
        if not jvm_flags:
            jvm_flags = sstats.get("java", {}).get("flags", "")
        if jvm_flags:
            result["jvm_flags"] = jvm_flags

    if pstats:
        mem = pstats.get("memory", {})
        if mem:
            heap = mem.get("heap", {})
            if heap:
                result["heap"] = {
                    "used": heap.get("used"),
                    "committed": heap.get("committed", heap.get("total")),
                    "max": heap.get("max"),
                }
        gc_map = pstats.get("gc", {})
        if gc_map:
            result["gc"] = {}
            for name, gc in gc_map.items():
                result["gc"][name] = {
                    "total_collections": gc.get("total"),
                    "avg_time_ms": gc.get("avg_time", gc.get("avgTime")),
                    "avg_frequency": gc.get("avg_frequency", gc.get("avgFrequency")),
                }

    if sources:
        result["plugins_mods"] = {}
        for name, info in sources.items():
            result["plugins_mods"][name] = {
                "name": info.get("name", name),
                "version": info.get("version", "unknown"),
                "author": info.get("author", ""),
                "description": info.get("description", ""),
            }

    sampler_meta = meta.get("dataAggregator", meta.get("data_aggregator", {}))
    if sampler_meta:
        mode = meta.get("samplerMode", meta.get("sampler_mode"))
        engine = meta.get("samplerEngine", meta.get("sampler_engine"))
        if isinstance(mode, int):
            mode = SAMPLER_MODE_MAP.get(mode, mode)
        if isinstance(engine, int):
            engine = SAMPLER_ENGINE_MAP.get(engine, engine)
        agg_type = sampler_meta.get("type")
        if isinstance(agg_type, int):
            agg_type = AGGREGATOR_TYPE_MAP.get(agg_type, agg_type)
        tg = sampler_meta.get("threadGrouper", sampler_meta.get("thread_grouper"))
        if isinstance(tg, int):
            tg = THREAD_GROUPER_MAP.get(tg, tg)
        result["sampler"] = {
            "interval_ms": meta.get("interval", 4),
            "mode": mode,
            "engine": engine,
            "aggregator_type": agg_type,
            "thread_grouper": tg,
            "tick_threshold": sampler_meta.get("tickLengthThreshold", sampler_meta.get("tick_length_threshold")),
            "included_ticks": sampler_meta.get("numberOfIncludedTicks", sampler_meta.get("number_of_included_ticks")),
        }

    return result


def cmd_threads(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    threads = get_threads(data)
    if not threads:
        return {"error": "No thread data found. Use --full flag when fetching URL data."}

    result = {"total_threads": len(threads), "threads": []}
    thread_filters = args.thread if args.thread else None

    meta = get_metadata(data)
    sstats = get_system_stats(meta)

    for t in threads:
        name = t.get("name", "unknown")
        if not thread_matches(name, thread_filters):
            continue

        times = t.get("times", [])
        total_time = sum(times) if times else 0
        children = t.get("children", [])

        child_time = sum(sum(c.get("times", [])) for c in children if c.get("times"))
        sleep_time = 0
        native_idle_time = 0
        tick_time = 0
        tick_names = {"tick", "doTick", "runTick"}
        is_folia_thread = _is_folia_region_thread(name)

        def _walk_frames(node, depth=0):
            nonlocal sleep_time, native_idle_time, tick_time
            cn = node.get("className", node.get("class_name", ""))
            mn = node.get("methodName", node.get("method_name", ""))
            ct = sum(node.get("times", [])) if node.get("times") else 0
            if any(tk in mn for tk in tick_names):
                tick_time += ct
            mn_lower = mn.lower()
            cn_lower = cn.lower()
            is_sleep = any(s in mn_lower for s in SLEEP_METHODS)
            is_native_idle = any(s in mn_lower or s in cn_lower for s in NATIVE_IDLE_METHODS)
            is_folia_idle = any(p in (cn_lower + "." + mn_lower) for p in FOLIA_CANVAS_IDLE_PATTERNS)
            if is_sleep:
                sleep_time += ct
            if is_native_idle or (is_folia_idle and is_folia_thread):
                native_idle_time += ct
            for child in node.get("children", []):
                _walk_frames(child, depth + 1)

        for c in children:
            _walk_frames(c)

        effective_idle = sleep_time + native_idle_time
        effective_idle_pct = pct(effective_idle, total_time)
        active_time = total_time - effective_idle
        active_pct = pct(active_time, total_time)

        entry = {
            "name": name,
            "total_time": total_time,
            "sleep_time": sleep_time,
            "native_idle_time": native_idle_time,
            "effective_idle_time": effective_idle,
            "effective_idle_pct": effective_idle_pct,
            "active_time": active_time,
            "active_pct": active_pct,
            "tick_time": tick_time,
            "tick_pct": pct(tick_time, total_time),
            "other_time": total_time - effective_idle - tick_time,
            "child_count": len(children),
            "is_folia_region_thread": is_folia_thread,
        }

        if effective_idle_pct >= 50:
            entry["health"] = "HEALTHY"
        elif effective_idle_pct >= 20:
            entry["health"] = "MODERATE"
        else:
            entry["health"] = "OVERLOADED"

        sleep_pct_val = pct(sleep_time, total_time)
        entry["sleep_pct"] = sleep_pct_val

        if args.top is not None and args.top > 0:
            entry["top_children"] = []
            sorted_children = sorted(children, key=lambda c: -sum(c.get("times", [])))
            for child in sorted_children[:args.top]:
                cn = child.get("className", child.get("class_name", ""))
                mn = child.get("methodName", child.get("method_name", ""))
                ct = sum(child.get("times", []))
                entry["top_children"].append({
                    "class": cn,
                    "method": mn,
                    "time": ct,
                    "pct": pct(ct, total_time),
                })

        result["threads"].append(entry)

    result["matched_threads"] = len(result["threads"])
    result["threads"].sort(key=lambda t: -t["total_time"])

    if args.top_threads:
        result["threads"] = result["threads"][:args.top_threads]

    return result


def cmd_tree(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    threads = get_threads(data)
    if not threads:
        return {"error": "No thread data found."}

    thread_filters = args.thread if args.thread else None
    results = []

    for t in threads:
        name = t.get("name", "unknown")
        if not thread_matches(name, thread_filters):
            continue

        times = t.get("times", [])
        total_time = sum(times) if times else 0

        children = t.get("children", [])
        node_entries = []
        for child in children:
            if args.plugin and not node_matches_class(child, args.plugin):
                continue
            entries = walk_tree(
                child, depth=1, total_time=total_time,
                min_pct=args.min_pct, max_depth=args.max_depth,
                class_filter=args.class_filter,
            )
            node_entries.extend(entries)

        if args.sort_by_pct:
            node_entries.sort(key=lambda e: -e.get("time_pct", 0))

        result = {
            "thread": name,
            "total_time": total_time,
            "nodes": node_entries[:args.limit] if args.limit else node_entries,
            "total_nodes_found": len(node_entries),
        }
        results.append(result)

    return {"threads": results}


def cmd_hotspots(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    threads = get_threads(data)
    if not threads:
        return {"error": "No thread data found."}

    thread_filters = args.thread if args.thread else None
    all_hotspots = []

    for t in threads:
        name = t.get("name", "unknown")
        if not thread_matches(name, thread_filters):
            continue

        times = t.get("times", [])
        total_time = sum(times) if times else 0
        if total_time == 0:
            continue

        for child in t.get("children", []):
            hotspots = find_hotspots(child, total_time, min_pct=args.min_pct)
            for h in hotspots:
                h["thread"] = name
                if args.class_filter:
                    sig = f"{h['class']}.{h['method']}".lower()
                    if args.class_filter.lower() not in sig:
                        continue
                if args.exclude_sleep:
                    if _is_idle_frame(h["class"], h["method"]):
                        continue
                all_hotspots.append(h)

    all_hotspots.sort(key=lambda h: -h["self_pct"])

    result = {
        "hotspots": all_hotspots[:args.limit],
        "total_found": len(all_hotspots),
    }
    return result


def cmd_plugins(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    threads = get_threads(data)
    if not threads:
        return {"error": "No thread data found."}

    class_sources = get_class_sources(data)
    method_sources = get_method_sources(data)
    meta = get_metadata(data)
    sources_meta = get_sources(meta)

    thread_filters = args.thread if args.thread else None
    source_totals = defaultdict(float)

    for t in threads:
        name = t.get("name", "unknown")
        if not thread_matches(name, thread_filters):
            continue
        times = t.get("times", [])
        total_time = sum(times) if times else 0
        if total_time == 0:
            continue

        for child in t.get("children", []):
            attrs = attribute_to_source(child, class_sources, method_sources, sources_meta)
            for d in attrs:
                for k, v in d.items():
                    source_totals[k] += v

    grand_total = sum(source_totals.values()) or 1
    results = []
    for name, time_val in sorted(source_totals.items(), key=lambda x: -x[1]):
        if args.plugin and args.plugin.lower() not in name.lower():
            continue
        results.append({
            "source": name,
            "time": time_val,
            "pct": pct(time_val, grand_total),
        })

    return {"sources": results, "grand_total": grand_total}


def cmd_tps(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    meta = get_metadata(data)
    pstats = get_platform_stats(meta)

    result = {}
    if pstats.get("tps"):
        t = pstats["tps"]
        result["tps"] = {
            "1m": {"value": t.get("last1m"), "status": assess_tps(t.get("last1m", 0))},
            "5m": {"value": t.get("last5m"), "status": assess_tps(t.get("last5m", 0))},
            "15m": {"value": t.get("last15m"), "status": assess_tps(t.get("last15m", 0))},
            "target": t.get("gameTargetTps", t.get("game_target_tps", 20)),
        }

    if pstats.get("mspt"):
        m = pstats["mspt"]
        for window_key in ["last1m", "last5m"]:
            w = m.get(window_key, {})
            if w:
                result[f"mspt_{window_key}"] = {
                    "mean": w.get("mean"),
                    "median": w.get("median"),
                    "p95": w.get("percentile95"),
                    "max": w.get("max"),
                    "min": w.get("min"),
                    "median_status": assess_mspt(w.get("median", 999)),
                    "p95_status": assess_mspt(w.get("percentile95", 999)),
                    "max_status": assess_mspt(w.get("max", 999)),
                }
        result["ideal_mspt"] = m.get("gameMaxIdealMspt", m.get("game_max_ideal_mspt", 50))

    window_stats = get_window_stats(data)
    if window_stats:
        result["windows"] = []
        for wid, ws in sorted(window_stats.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
            result["windows"].append({
                "window_id": wid,
                "ticks": ws.get("ticks"),
                "tps": ws.get("tps"),
                "tps_status": assess_tps(ws.get("tps", 0)),
                "mspt_median": ws.get("mspt_median"),
                "mspt_max": ws.get("mspt_max"),
                "mspt_median_status": assess_mspt(ws.get("mspt_median", 999)),
                "mspt_max_status": assess_mspt(ws.get("mspt_max", 999)),
                "players": ws.get("players"),
                "entities": ws.get("entities"),
                "duration": ws.get("duration"),
            })

    return result


def cmd_gc(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    meta = get_metadata(data)
    pstats = get_platform_stats(meta)
    sstats = get_system_stats(meta)

    result = {}

    for stats_key, stats in [("platform", pstats), ("system", sstats)]:
        gc_map = stats.get("gc", {})
        if gc_map:
            result[stats_key] = {}
            for name, gc in gc_map.items():
                freq = gc.get("avg_frequency", gc.get("avgFrequency", 0))
                avg_t = gc.get("avg_time", gc.get("avgTime", 0))
                freq_status = "GOOD"
                if freq > 5:
                    freq_status = "CRITICAL"
                elif freq > 1:
                    freq_status = "WARNING"
                avg_status = "GOOD"
                if avg_t > 200:
                    avg_status = "CRITICAL"
                elif avg_t > 50:
                    avg_status = "WARNING"
                result[stats_key][name] = {
                    "total_collections": gc.get("total"),
                    "avg_time_ms": avg_t,
                    "avg_frequency_per_min": freq,
                    "avg_time_status": avg_status,
                    "avg_frequency_status": freq_status,
                }

    if not result:
        return {"info": "No GC data found in this profile type"}

    return result


def cmd_health(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    result = {}
    meta = get_metadata(data)
    platform = get_platform_meta(meta)
    result["platform"] = platform

    pstats = get_platform_stats(meta)
    sstats = get_system_stats(meta)

    if pstats:
        tps = pstats.get("tps", {})
        mspt = pstats.get("mspt", {})
        if tps:
            result["tps"] = tps
        if mspt:
            result["mspt"] = mspt
        gc = pstats.get("gc", {})
        if gc:
            result["gc_platform"] = gc
        mem = pstats.get("memory", {})
        if mem:
            result["memory_heap"] = mem.get("heap", {})
            result["memory_non_heap"] = mem.get("non_heap", mem.get("nonHeap", {}))

    if sstats:
        result["cpu"] = sstats.get("cpu", {})
        result["os"] = sstats.get("os", {})
        result["java"] = sstats.get("java", {})
        result["disk"] = sstats.get("disk", {})
        gc = sstats.get("gc", {})
        if gc:
            result["gc_system"] = gc

    window_stats = get_window_stats(data)
    if window_stats:
        result["time_windows"] = []
        for wid, ws in sorted(window_stats.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
            result["time_windows"].append({"window_id": wid, **ws})

    return result


def cmd_heap(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    entries = data.get("entries", [])
    if not entries:
        return {"info": "No heap entries found in data"}

    total_size = sum(e.get("size", 0) for e in entries)
    total_instances = sum(e.get("instances", 0) for e in entries)

    sorted_entries = sorted(entries, key=lambda e: -e.get("size", 0))

    if args.type_filter:
        sorted_entries = [e for e in sorted_entries if args.type_filter.lower() in e.get("type", "").lower()]
    if args.plugin:
        sorted_entries = [e for e in sorted_entries if args.plugin.lower() in e.get("type", "").lower()]

    result_entries = []
    for e in sorted_entries[:args.limit]:
        result_entries.append({
            "type": e.get("type", "unknown"),
            "instances": e.get("instances", 0),
            "size_bytes": e.get("size", 0),
            "size_human": format_bytes(e.get("size", 0)),
            "size_pct": pct(e.get("size", 0), total_size),
            "instances_pct": pct(e.get("instances", 0), total_instances),
        })

    return {
        "total_types": len(entries),
        "total_instances": total_instances,
        "total_size_bytes": total_size,
        "total_size_human": format_bytes(total_size),
        "top_entries": result_entries,
    }


def cmd_entities(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    meta = get_metadata(data)
    pstats = get_platform_stats(meta)
    world = pstats.get("world", pstats.get("WorldStatistics", {}))

    if not world:
        return {"info": "No world/entity statistics found"}

    result = {
        "total_entities": world.get("totalEntities", world.get("total_entities", 0)),
        "entity_counts": world.get("entityCounts", world.get("entity_counts", {})),
        "worlds": [],
    }

    for w in world.get("worlds", []):
        w_entry = {
            "name": w.get("name", "unknown"),
            "total_entities": w.get("totalEntities", w.get("total_entities", 0)),
            "regions": [],
        }
        for r in w.get("regions", []):
            r_entry = {
                "total_entities": r.get("totalEntities", r.get("total_entities", 0)),
                "chunks": [],
            }
            for c in r.get("chunks", []):
                c_entry = {
                    "x": c.get("x"),
                    "z": c.get("z"),
                    "total_entities": c.get("totalEntities", c.get("total_entities", 0)),
                    "entity_counts": c.get("entityCounts", c.get("entity_counts", {})),
                }
                if args.entity_type:
                    ec = c_entry.get("entity_counts", {})
                    if args.entity_type.lower() not in str(ec).lower():
                        continue
                if args.min_entities and c_entry["total_entities"] < args.min_entities:
                    continue
                r_entry["chunks"].append(c_entry)
            w_entry["regions"].append(r_entry)
        result["worlds"].append(w_entry)

    return result


def cmd_search(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    threads = get_threads(data)
    if not threads:
        return {"error": "No thread data found."}

    pattern = args.pattern
    is_regex = args.regex
    thread_filters = args.thread if args.thread else None
    matches = []

    def search_node(node, thread_name, path=None):
        if path is None:
            path = []
        cn = node.get("className", node.get("class_name", ""))
        mn = node.get("methodName", node.get("method_name", ""))
        sig = f"{cn}.{mn}"
        current_path = path + [sig]

        if is_regex:
            hit = bool(re.search(pattern, sig, re.IGNORECASE))
        else:
            hit = pattern.lower() in sig.lower()

        if hit:
            times = node.get("times", [])
            total = sum(times) if times else 0
            matches.append({
                "class": cn,
                "method": mn,
                "line": node.get("lineNumber", node.get("line_number")),
                "time": total,
                "thread": thread_name,
                "path": " -> ".join(current_path),
                "depth": len(current_path),
            })

        for child in node.get("children", []):
            search_node(child, thread_name, current_path)

    for t in threads:
        name = t.get("name", "unknown")
        if not thread_matches(name, thread_filters):
            continue
        for child in t.get("children", []):
            search_node(child, name)

    matches.sort(key=lambda m: -m["time"])

    if args.limit:
        matches = matches[:args.limit]

    return {"pattern": pattern, "regex": is_regex, "matches": matches, "total_found": len(matches)}


def cmd_callpath(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    threads = get_threads(data)
    if not threads:
        return {"error": "No thread data found."}

    pattern = args.method
    is_regex = args.regex
    thread_filters = args.thread if args.thread else None
    paths = []

    def find_path(node, target, current_path=None):
        if current_path is None:
            current_path = []
        cn = node.get("className", node.get("class_name", ""))
        mn = node.get("methodName", node.get("method_name", ""))
        sig = f"{cn}.{mn}"
        current_path = current_path + [{
            "class": cn,
            "method": mn,
            "line": node.get("lineNumber", node.get("line_number")),
            "time": sum(node.get("times", [])) if node.get("times") else 0,
        }]

        if is_regex:
            hit = bool(re.search(target, sig, re.IGNORECASE))
        else:
            hit = target.lower() in sig.lower()

        if hit:
            return current_path

        for child in node.get("children", []):
            result = find_path(child, target, current_path)
            if result:
                return result
        return None

    for t in threads:
        name = t.get("name", "unknown")
        if not thread_matches(name, thread_filters):
            continue
        times = t.get("times", [])
        total_time = sum(times) if times else 0

        for child in t.get("children", []):
            path = find_path(child, pattern)
            if path:
                paths.append({
                    "thread": name,
                    "thread_total_time": total_time,
                    "path": path,
                    "depth": len(path),
                    "self_time": path[-1]["time"] if path else 0,
                    "pct_of_thread": pct(path[-1]["time"] if path else 0, total_time),
                })

    paths.sort(key=lambda p: -p.get("pct_of_thread", 0))

    if args.limit:
        paths = paths[:args.limit]

    return {"target": pattern, "paths": paths, "total_found": len(paths)}


def cmd_compare(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    window_stats = get_window_stats(data)
    if not window_stats:
        return {"error": "No time window statistics found in data"}

    windows = sorted(window_stats.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0)

    if args.window_a is not None and args.window_b is not None:
        wa = window_stats.get(str(args.window_a), window_stats.get(args.window_a))
        wb = window_stats.get(str(args.window_b), window_stats.get(args.window_b))
    else:
        if len(windows) < 2:
            return {"error": "Need at least 2 time windows to compare"}
        wa = windows[0][1]
        wb = windows[-1][1]
        args.window_a = windows[0][0]
        args.window_b = windows[-1][0]

    if not wa or not wb:
        return {"error": f"Could not find window data for {args.window_a} or {args.window_b}"}

    def delta(a, b):
        if a is None or b is None:
            return None
        if b == 0:
            return None
        return round((a - b) / b * 100, 2) if b != 0 else 0

    result = {
        "window_a": args.window_a,
        "window_b": args.window_b,
        "comparison": {},
    }

    fields = ["tps", "mspt_median", "mspt_max", "cpu_process", "cpu_system", "players", "entities", "tile_entities", "chunks"]
    for f in fields:
        va = wa.get(f)
        vb = wb.get(f)
        result["comparison"][f] = {
            "window_a": va,
            "window_b": vb,
            "change_pct": delta(va, vb),
        }

    return result


def cmd_report(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    meta = get_metadata(data)
    ptype = get_profile_type(data)
    platform = get_platform_meta(meta)
    pstats = get_platform_stats(meta)
    sstats = get_system_stats(meta)
    sources_meta = get_sources(meta)
    threads = get_threads(data)
    class_sources = get_class_sources(data)
    method_sources = get_method_sources(data)

    report = {"profile_type": ptype, "platform": platform}

    if pstats:
        tps = pstats.get("tps", {})
        mspt = pstats.get("mspt", {})
        if tps:
            report["tps"] = tps
        if mspt:
            report["mspt"] = mspt

    gc_data = {}
    for stats in [pstats, sstats]:
        for name, gc in stats.get("gc", {}).items():
            gc_data[name] = gc
    if gc_data:
        report["gc"] = gc_data

    findings = []

    if pstats and pstats.get("tps"):
        for period, key in [("1m", "last1m"), ("5m", "last5m"), ("15m", "last15m")]:
            val = pstats["tps"].get(key, 20)
            if val < 15:
                findings.append({"severity": "CRITICAL", "category": "tps", "detail": f"TPS {period}m is {val}, server is severely lagging"})
            elif val < 19.5:
                findings.append({"severity": "WARNING", "category": "tps", "detail": f"TPS {period}m is {val}, below ideal 20"})

    if pstats and pstats.get("mspt"):
        for period, key in [("1m", "last1m"), ("5m", "last5m")]:
            w = pstats["mspt"].get(key, {})
            p95 = w.get("percentile95", 0)
            mx = w.get("max", 0)
            if mx > 150:
                findings.append({"severity": "CRITICAL", "category": "lag_spike", "detail": f"MSPT {period}m max is {mx}ms, severe lag spikes detected"})
            elif mx > 50:
                findings.append({"severity": "WARNING", "category": "lag_spike", "detail": f"MSPT {period}m max is {mx}ms, occasional lag spikes"})
            if p95 > 60:
                findings.append({"severity": "WARNING", "category": "mspt", "detail": f"MSPT {period}m P95 is {p95}ms, ticks are consistently slow"})

    if threads:
        for t in threads:
            name = t.get("name", "unknown")
            if "server" not in name.lower() and "main" not in name.lower():
                continue
            times = t.get("times", [])
            total_time = sum(times) if times else 0
            children = t.get("children", [])
            sleep_time = 0
            for c in children:
                cn = c.get("className", c.get("class_name", ""))
                mn = c.get("methodName", c.get("method_name", ""))
                if _is_idle_frame(cn, mn):
                    sleep_time += sum(c.get("times", []))
            sleep_pct = pct(sleep_time, total_time)
            if sleep_pct < 5:
                findings.append({"severity": "CRITICAL", "category": "overloaded", "detail": f"Server thread sleep only {sleep_pct}%, server has no spare capacity"})
            elif sleep_pct < 20:
                findings.append({"severity": "WARNING", "category": "overloaded", "detail": f"Server thread sleep only {sleep_pct}%, server is working very hard"})
            break

    if gc_data:
        for name, gc in gc_data.items():
            freq = gc.get("avg_frequency", gc.get("avgFrequency", 0))
            avg_t = gc.get("avg_time", gc.get("avgTime", 0))
            if freq > 5:
                findings.append({"severity": "CRITICAL", "category": "gc", "detail": f"GC '{name}' frequency {freq}/min is very high"})
            elif freq > 1:
                findings.append({"severity": "WARNING", "category": "gc", "detail": f"GC '{name}' frequency {freq}/min is elevated"})
            if avg_t > 200:
                findings.append({"severity": "CRITICAL", "category": "gc_pause", "detail": f"GC '{name}' avg pause {avg_t}ms is very long"})
            elif avg_t > 50:
                findings.append({"severity": "WARNING", "category": "gc_pause", "detail": f"GC '{name}' avg pause {avg_t}ms is elevated"})

    if threads:
        for t in threads:
            name = t.get("name", "unknown")
            times = t.get("times", [])
            total_time = sum(times) if times else 0
            if total_time == 0:
                continue
            hotspots = []
            for child in t.get("children", []):
                hotspots.extend(find_hotspots(child, total_time, min_pct=3.0))
            hotspots.sort(key=lambda h: -h["self_pct"])
            report.setdefault(f"top_hotspots_{name}", hotspots[:10])

    if class_sources or method_sources or sources_meta:
        source_totals = defaultdict(float)
        for t in threads:
            times = t.get("times", [])
            for child in t.get("children", []):
                attrs = attribute_to_source(child, class_sources, method_sources, sources_meta)
                for d in attrs:
                    for k, v in d.items():
                        source_totals[k] += v
        grand = sum(source_totals.values()) or 1
        report["sources_breakdown"] = sorted(
            [{"source": k, "pct": pct(v, grand)} for k, v in source_totals.items()],
            key=lambda x: -x["pct"],
        )

    report["findings"] = sorted(findings, key=lambda f: {"CRITICAL": 0, "WARNING": 1, "LOW": 2}.get(f["severity"], 3))

    return report


def _detect_gc_type(gc_names):
    gc_types = set()
    for name in gc_names:
        n = name.lower()
        if "zgc" in n:
            gc_types.add("ZGC")
        elif "g1" in n:
            gc_types.add("G1GC")
        elif "cms" in n:
            gc_types.add("CMS")
        elif "parallel" in n or "ps" in n:
            gc_types.add("Parallel")
    return gc_types


def _get_gc_role(name):
    n = name.lower()
    if "pause" in n:
        return "STW_PAUSE"
    if "cycle" in n or "old" in n or "major" in n:
        return "CONCURRENT_CYCLE"
    if "young" in n or "minor" in n:
        return "YOUNG_GEN"
    return "UNKNOWN"


def cmd_analyze_gc(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    meta = get_metadata(data)
    pstats = get_platform_stats(meta)
    sstats = get_system_stats(meta)
    jvm_flags = meta.get("serverConfigurations", meta.get("server_configurations", {}))

    result = {"gc_collectors": {}, "analysis": {}, "recommendations": []}

    all_gc = {}
    for stats_key, stats in [("platform", pstats), ("system", sstats)]:
        gc_map = stats.get("gc", {})
        for name, gc in gc_map.items():
            key = f"{stats_key}:{name}"
            freq = gc.get("avg_frequency", gc.get("avgFrequency", 0))
            avg_t = gc.get("avg_time", gc.get("avgTime", 0))
            total = gc.get("total", 0)
            role = _get_gc_role(name)
            is_stw = role == "STW_PAUSE"
            is_zgc_cycle = "zgc" in name.lower() and role == "CONCURRENT_CYCLE"

            collector = {
                "name": name,
                "source": stats_key,
                "role": role,
                "is_stw": is_stw,
                "total_collections": total,
                "avg_time_ms": avg_t,
                "avg_frequency_per_min": freq,
            }

            if is_stw or not is_zgc_cycle:
                if freq > 5:
                    collector["frequency_status"] = "CRITICAL"
                elif freq > 1:
                    collector["frequency_status"] = "WARNING"
                else:
                    collector["frequency_status"] = "GOOD"
            else:
                if freq > 1:
                    collector["frequency_status"] = "WARNING"
                else:
                    collector["frequency_status"] = "GOOD"

            if is_stw:
                if avg_t > 200:
                    collector["pause_status"] = "CRITICAL"
                elif avg_t > 50:
                    collector["pause_status"] = "WARNING"
                else:
                    collector["pause_status"] = "GOOD"
            elif is_zgc_cycle:
                collector["pause_status"] = "N/A_CONCURRENT"
            else:
                if avg_t > 500:
                    collector["pause_status"] = "CRITICAL"
                elif avg_t > 100:
                    collector["pause_status"] = "WARNING"
                else:
                    collector["pause_status"] = "GOOD"

            all_gc[key] = collector

    result["gc_collectors"] = all_gc

    gc_types = _detect_gc_type([n for n in all_gc])
    result["analysis"]["detected_gc_type"] = list(gc_types) if gc_types else ["Unknown"]

    heap_info = pstats.get("memory", {}).get("heap", {})
    heap_max = heap_info.get("max", 0)
    heap_used = heap_info.get("used", 0)

    if heap_max > 0:
        heap_pct = round(heap_used / heap_max * 100, 1)
        result["analysis"]["heap_usage_pct"] = heap_pct
        if heap_pct > 90:
            result["analysis"]["heap_pressure"] = "CRITICAL"
        elif heap_pct > 75:
            result["analysis"]["heap_pressure"] = "WARNING"
        else:
            result["analysis"]["heap_pressure"] = "GOOD"

    flags_str = str(jvm_flags)
    result["analysis"]["jvm_flags"] = flags_str if flags_str else "Not available from profile data"

    if "ZGC" in gc_types:
        stw_pauses = [c for c in all_gc.values() if "zgc" in c["name"].lower() and c["is_stw"]]
        concurrent_cycles = [c for c in all_gc.values() if "zgc" in c["name"].lower() and c["role"] == "CONCURRENT_CYCLE"]
        if stw_pauses:
            max_pause_freq = max(c["avg_frequency_per_min"] for c in stw_pauses)
            max_pause_time = max(c["avg_time_ms"] for c in stw_pauses)
            result["analysis"]["zgc_stw_pause_max_freq"] = max_pause_freq
            result["analysis"]["zgc_stw_pause_max_time_ms"] = max_pause_time
            if max_pause_time > 1:
                result["recommendations"].append({
                    "severity": "WARNING",
                    "detail": f"ZGC STW pauses averaging {max_pause_time:.2f}ms should be sub-millisecond. Check -XX:ZCollectionInterval and heap sizing.",
                })
            if max_pause_freq > 10:
                result["recommendations"].append({
                    "severity": "CRITICAL",
                    "detail": f"ZGC minor pauses at {max_pause_freq:.1f}/min is very high, indicating high allocation rate or insufficient heap. Consider increasing heap or reducing allocation.",
                })
        if concurrent_cycles:
            for c in concurrent_cycles:
                result["recommendations"].append({
                    "severity": "INFO",
                    "detail": f"ZGC '{c['name']}' avg cycle time {c['avg_time_ms']:.1f}ms is CONCURRENT (not STW). This does NOT directly cause TPS loss.",
                })

    if "G1GC" in gc_types:
        young_gc = [c for c in all_gc.values() if "g1" in c["name"].lower() and c["role"] == "YOUNG_GEN"]
        if young_gc:
            for c in young_gc:
                if c["avg_time_ms"] > 200:
                    result["recommendations"].append({
                        "severity": "CRITICAL",
                        "detail": f"G1 young gen pause {c['avg_time_ms']:.1f}ms exceeds 200ms target. Use Aikar's flags or increase -XX:G1NewSizePercent.",
                    })

    if not result["recommendations"]:
        stw_issues = [c for c in all_gc.values() if c.get("pause_status") in ("CRITICAL", "WARNING") and c["is_stw"]]
        freq_issues = [c for c in all_gc.values() if c.get("frequency_status") in ("CRITICAL", "WARNING")]
        if not stw_issues and not freq_issues:
            result["recommendations"].append({"severity": "INFO", "detail": "GC health appears good. No immediate tuning required."})

    return result


def cmd_analyze_tps(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    meta = get_metadata(data)
    pstats = get_platform_stats(meta)
    window_stats = get_window_stats(data)

    result = {"overall": {}, "windows_analysis": [], "lag_spikes": [], "recommendations": []}

    tps_data = pstats.get("tps", {})
    mspt_data = pstats.get("mspt", {})

    if tps_data:
        for period, key in [("1m", "last1m"), ("5m", "last5m"), ("15m", "last15m")]:
            val = tps_data.get(key, 0)
            result["overall"][f"tps_{period}"] = {"value": val, "status": assess_tps(val)}

    if mspt_data:
        for period, key in [("1m", "last1m"), ("5m", "last5m")]:
            w = mspt_data.get(key, {})
            if w:
                med = w.get("median", 0)
                p95 = w.get("percentile95", 0)
                mx = w.get("max", 0)
                result["overall"][f"mspt_{period}"] = {
                    "median": med, "p95": p95, "max": mx,
                    "median_status": assess_mspt(med),
                    "p95_status": assess_mspt(p95),
                    "max_status": assess_mspt(mx),
                }
                if mx > 0 and med > 0:
                    spike_ratio = round(mx / med, 1) if med > 0 else 0
                    if spike_ratio > 3:
                        result["lag_spikes"].append({
                            "period": period,
                            "median_ms": med,
                            "max_ms": mx,
                            "spike_ratio": spike_ratio,
                            "severity": "CRITICAL" if spike_ratio > 5 else "WARNING",
                            "detail": f"MSPT max ({mx}ms) is {spike_ratio}x the median ({med}ms), indicating severe lag spikes",
                        })

    if window_stats:
        sorted_windows = sorted(window_stats.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0)
        tps_values = []
        entity_values = []
        player_values = []

        for wid, ws in sorted_windows:
            t = ws.get("tps", 0)
            e = ws.get("entities", 0)
            p = ws.get("players", 0)
            mspt_med = ws.get("mspt_median", 0)
            mspt_mx = ws.get("mspt_max", 0)
            tps_values.append(t)
            entity_values.append(e)
            player_values.append(p)

            w_analysis = {
                "window_id": wid,
                "tps": t, "tps_status": assess_tps(t),
                "mspt_median": mspt_med, "mspt_max": mspt_mx,
                "players": p, "entities": e,
                "duration": ws.get("duration"),
            }
            if t < 19:
                w_analysis["lag_detected"] = True
                w_analysis["severity"] = "CRITICAL" if t < 15 else "WARNING"

            result["windows_analysis"].append(w_analysis)

        if len(tps_values) > 2:
            min_tps = min(tps_values)
            max_tps = max(tps_values)
            tps_variability = round(max_tps - min_tps, 2)
            result["analysis"] = {
                "tps_range": f"{min_tps:.2f} - {max_tps:.2f}",
                "tps_variability": tps_variability,
                "avg_entities": round(sum(entity_values) / len(entity_values)),
                "avg_players": round(sum(player_values) / len(player_values)),
            }

            low_tps_windows = [w for w in result["windows_analysis"] if w.get("tps", 20) < 19]
            if low_tps_windows:
                result["recommendations"].append({
                    "severity": "WARNING",
                    "detail": f"{len(low_tps_windows)} of {len(result['windows_analysis'])} time windows had TPS < 19. Check entity counts and player load during those windows.",
                })

            if tps_variability > 1:
                result["recommendations"].append({
                    "severity": "INFO",
                    "detail": f"TPS variability is {tps_variability:.2f}. High variability suggests intermittent load spikes rather than sustained overload.",
                })

    if not result["recommendations"]:
        result["recommendations"].append({"severity": "INFO", "detail": "TPS appears stable and healthy across all windows."})

    return result


def cmd_analyze_cpu(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    meta = get_metadata(data)
    pstats = get_platform_stats(meta)
    sstats = get_system_stats(meta)

    result = {"cpu_analysis": {}, "recommendations": []}

    cpu = sstats.get("cpu", {})
    if cpu:
        proc_1m = cpu.get("processUsage", cpu.get("process_usage", {})).get("last1m", 0)
        sys_1m = cpu.get("systemUsage", cpu.get("system_usage", {})).get("last1m", 0)
        model = cpu.get("modelName", cpu.get("model_name", "unknown"))
        threads = cpu.get("threads", 0)

        result["cpu_analysis"] = {
            "model": model,
            "threads": threads,
            "process_usage_1m": round(proc_1m * 100, 1),
            "system_usage_1m": round(sys_1m * 100, 1),
        }

        if proc_1m > 0.8:
            result["cpu_analysis"]["process_status"] = "CRITICAL"
            result["recommendations"].append({
                "severity": "CRITICAL",
                "detail": f"Server process using {proc_1m*100:.1f}% CPU. Server is CPU-bound. Reduce view-distance, entity counts, or optimize plugins.",
            })
        elif proc_1m > 0.5:
            result["cpu_analysis"]["process_status"] = "WARNING"
            result["recommendations"].append({
                "severity": "WARNING",
                "detail": f"Server process using {proc_1m*100:.1f}% CPU. Getting close to limits. Monitor for spikes.",
            })
        else:
            result["cpu_analysis"]["process_status"] = "GOOD"

        if sys_1m > 0.9:
            result["cpu_analysis"]["system_status"] = "CRITICAL"
            result["recommendations"].append({
                "severity": "CRITICAL",
                "detail": f"Total system CPU at {sys_1m*100:.1f}%. Other processes on host consuming resources. Consider dedicated hosting.",
            })
        elif sys_1m > 0.7:
            result["cpu_analysis"]["system_status"] = "WARNING"
        else:
            result["cpu_analysis"]["system_status"] = "GOOD"

        if proc_1m > 0.3 and sys_1m > 0.9:
            other_pct = round((sys_1m - proc_1m) * 100, 1)
            result["recommendations"].append({
                "severity": "WARNING",
                "detail": f"Other processes using ~{other_pct}% CPU. Host has competing workloads. Check for background tasks, backups, or other servers.",
            })

    threads = get_threads(data)
    if threads:
        total_thread_time = sum(sum(t.get("times", [])) for t in threads)
        top_threads = sorted(threads, key=lambda t: -sum(t.get("times", [])))
        result["thread_cpu"] = []
        for t in top_threads[:10]:
            total = sum(t.get("times", []))
            result["thread_cpu"].append({
                "name": t.get("name"),
                "total_time": total,
                "pct_of_total": pct(total, total_thread_time),
            })

    if not result["recommendations"]:
        result["recommendations"].append({"severity": "INFO", "detail": "CPU usage appears healthy."})

    return result


def cmd_pipeline(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    threads = get_threads(data)
    if not threads:
        return {"error": "No thread data found."}

    thread_filters = args.thread if args.thread else ["netty"]
    netty_threads = [t for t in threads if thread_matches(t.get("name", ""), thread_filters)]

    if not netty_threads:
        return {"error": "No netty threads found. Use --thread to specify thread name containing 'netty'."}

    result = {"handlers": [], "duplicate_warnings": []}
    handler_set = {}

    for t in netty_threads:
        name = t.get("name", "unknown")
        times = t.get("times", [])
        total_time = sum(times) if times else 0

        def find_pipeline_handlers(node, depth=0, pipeline_path=None):
            if pipeline_path is None:
                pipeline_path = []
            cn = node.get("className", node.get("class_name", ""))
            mn = node.get("methodName", node.get("method_name", ""))
            ct = sum(node.get("times", [])) if node.get("times") else 0
            sig = f"{cn}.{mn}"
            current_path = pipeline_path + [sig]

            is_handler = False
            cn_lower = cn.lower()
            handler_keywords = ["handler", "channel", "pipeline", "encoder", "decoder", "packet", "connection", "protocol"]
            if any(kw in cn_lower for kw in handler_keywords):
                is_handler = True
            if "netty" in cn_lower:
                is_handler = True

            if is_handler and depth > 0:
                handler_entry = {
                    "class": cn,
                    "method": mn,
                    "time": ct,
                    "pct": pct(ct, total_time),
                    "thread": name,
                    "depth": depth,
                    "path": " -> ".join(current_path),
                }
                result["handlers"].append(handler_entry)
                short_name = cn.split(".")[-1]
                if short_name in handler_set:
                    handler_set[short_name].append(cn)
                else:
                    handler_set[short_name] = [cn]

            for child in node.get("children", []):
                find_pipeline_handlers(child, depth + 1, current_path)

        for child in t.get("children", []):
            find_pipeline_handlers(child)

    if args.detect_duplicates:
        for hname, classes in handler_set.items():
            unique_classes = list(set(classes))
            if len(unique_classes) > 1:
                result["duplicate_warnings"].append({
                    "handler_short_name": hname,
                    "classes": unique_classes,
                    "count": len(unique_classes),
                    "detail": f"{hname} has {len(unique_classes)} different implementations in the pipeline - possible shaded duplicate",
                })

    result["total_handlers"] = len(result["handlers"])
    result["unique_handler_names"] = len(handler_set)
    result["threads_analyzed"] = [t.get("name", "unknown") for t in netty_threads]

    return result


def cmd_plugin_heap(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    entries = data.get("entries", [])
    if not entries:
        return {"info": "No heap entries found in data"}

    plugin_name = args.plugin
    if not plugin_name:
        return {"error": "Plugin name required. Use --plugin <name>"}

    class_sources = get_class_sources(data)
    meta = get_metadata(data)
    sources_meta = get_sources(meta)

    plugin_classes = set()
    for cls, src_name in class_sources.items():
        src_info = sources_meta.get(src_name, {})
        src_label = src_info.get("name", src_name)
        if plugin_name.lower() in src_label.lower() or plugin_name.lower() in cls.lower():
            plugin_classes.add(cls)

    total_size = sum(e.get("size", 0) for e in entries)
    total_instances = sum(e.get("instances", 0) for e in entries)

    plugin_entries = []
    plugin_size = 0
    plugin_instances = 0
    for e in entries:
        type_name = e.get("type", "")
        matched = False
        for cls in plugin_classes:
            if cls.lower() in type_name.lower():
                matched = True
                break
        if not matched and plugin_name.lower() in type_name.lower():
            matched = True
        if matched:
            plugin_size += e.get("size", 0)
            plugin_instances += e.get("instances", 0)
            plugin_entries.append({
                "type": type_name,
                "instances": e.get("instances", 0),
                "size_bytes": e.get("size", 0),
                "size_human": format_bytes(e.get("size", 0)),
                "pct_of_total": pct(e.get("size", 0), total_size),
            })

    plugin_entries.sort(key=lambda e: -e["size_bytes"])

    pct_of_heap = pct(plugin_size, total_size)
    assessment = "GOOD"
    if pct_of_heap > 10:
        assessment = "CRITICAL"
    elif pct_of_heap > 5:
        assessment = "WARNING"

    return {
        "plugin": plugin_name,
        "plugin_heap_bytes": plugin_size,
        "plugin_heap_human": format_bytes(plugin_size),
        "pct_of_total_heap": pct_of_heap,
        "assessment": assessment,
        "plugin_instances": plugin_instances,
        "matched_classes": len(plugin_classes),
        "top_entries": plugin_entries[:args.limit],
    }


def cmd_plugin_profile(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    plugin_name = args.plugin
    if not plugin_name:
        return {"error": "Plugin name required. Use --plugin <name>"}

    meta = get_metadata(data)
    pstats = get_platform_stats(meta)
    threads = get_threads(data)
    class_sources = get_class_sources(data)
    method_sources = get_method_sources(data)
    sources_meta = get_sources(meta)

    result = {"plugin": plugin_name}

    source_totals = defaultdict(float)
    for t in threads:
        times = t.get("times", [])
        total_time = sum(times) if times else 0
        for child in t.get("children", []):
            attrs = attribute_to_source(child, class_sources, method_sources, sources_meta)
            for d in attrs:
                for k, v in d.items():
                    if plugin_name.lower() in k.lower():
                        source_totals[k] += v

    grand_total = sum(sum(t.get("times", [])) for t in threads) or 1
    plugin_time = sum(source_totals.values())
    result["cpu"] = {
        "total_time": plugin_time,
        "pct_of_total": pct(plugin_time, grand_total),
        "sources": {k: pct(v, grand_total) for k, v in source_totals.items()},
    }

    cpu_pct = pct(plugin_time, grand_total)
    if cpu_pct > 20:
        result["cpu"]["assessment"] = "CRITICAL"
    elif cpu_pct > 5:
        result["cpu"]["assessment"] = "WARNING"
    else:
        result["cpu"]["assessment"] = "LOW"

    entries = data.get("entries", [])
    if entries:
        total_size = sum(e.get("size", 0) for e in entries)
        plugin_size = 0
        plugin_entries = []
        for e in entries:
            type_name = e.get("type", "")
            if plugin_name.lower() in type_name.lower():
                plugin_size += e.get("size", 0)
                plugin_entries.append({"type": type_name, "size_bytes": e.get("size", 0), "instances": e.get("instances", 0)})
        plugin_entries.sort(key=lambda e: -e["size_bytes"])
        heap_pct = pct(plugin_size, total_size)
        result["heap"] = {
            "plugin_heap_bytes": plugin_size,
            "plugin_heap_human": format_bytes(plugin_size),
            "pct_of_total_heap": heap_pct,
            "assessment": "CRITICAL" if heap_pct > 10 else "WARNING" if heap_pct > 5 else "LOW",
            "top_entries": plugin_entries[:10],
        }

    hotspots_list = []
    for t in threads:
        times = t.get("times", [])
        total_time = sum(times) if times else 0
        for child in t.get("children", []):
            for h in find_hotspots(child, total_time, min_pct=0.5):
                cn = h.get("class", "")
                if plugin_name.lower() in cn.lower():
                    h["thread"] = t.get("name", "unknown")
                    hotspots_list.append(h)
    hotspots_list.sort(key=lambda h: -h.get("self_pct", 0))
    result["hotspots"] = hotspots_list[:20]

    findings = []
    if result["cpu"]["pct_of_total"] > 20:
        findings.append({"severity": "CRITICAL", "detail": f"{plugin_name} uses {result['cpu']['pct_of_total']}% of CPU time. This is very high and likely causing TPS issues."})
    elif result["cpu"]["pct_of_total"] > 5:
        findings.append({"severity": "WARNING", "detail": f"{plugin_name} uses {result['cpu']['pct_of_total']}% of CPU time. Monitor for performance impact."})
    if entries and result.get("heap", {}).get("pct_of_total_heap", 0) > 10:
        findings.append({"severity": "CRITICAL", "detail": f"{plugin_name} uses {result['heap']['pct_of_total_heap']}% of heap. Potential memory leak or bloat."})
    result["findings"] = findings

    return result


def cmd_recommend(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    meta = get_metadata(data)
    pstats = get_platform_stats(meta)
    sstats = get_system_stats(meta)
    threads = get_threads(data)
    platform = get_platform_meta(meta)

    result = {
        "platform": platform,
        "recommendations": [],
        "priority_actions": [],
    }

    gc_types = set()
    all_gc = {}
    for stats_key, stats in [("platform", pstats), ("system", sstats)]:
        for name, gc in stats.get("gc", {}).items():
            freq = gc.get("avg_frequency", gc.get("avgFrequency", 0))
            avg_t = gc.get("avg_time", gc.get("avgTime", 0))
            all_gc[f"{stats_key}:{name}"] = {"freq": freq, "avg_time": avg_t, "name": name}
            if "zgc" in name.lower():
                gc_types.add("ZGC")
            elif "g1" in name.lower():
                gc_types.add("G1GC")

    tps_data = pstats.get("tps", {})
    if tps_data:
        for key in ["last1m", "last5m", "last15m"]:
            val = tps_data.get(key, 20)
            if val < 15:
                result["recommendations"].append({"severity": "CRITICAL", "category": "tps", "detail": f"TPS {key} at {val:.1f} is critically low. Immediate action required.", "action": "Reduce entity counts, view-distance, or find lag-causing plugin via 'hotspots --thread server --exclude-sleep'"})
            elif val < 19.5:
                result["recommendations"].append({"severity": "WARNING", "category": "tps", "detail": f"TPS {key} at {val:.1f} is below ideal 20.", "action": "Run 'hotspots' and 'plugins' commands to identify what is consuming time."})

    heap_info = pstats.get("memory", {}).get("heap", {})
    if heap_info:
        used = heap_info.get("used", 0)
        mx = heap_info.get("max", 0)
        if mx > 0 and used > 0:
            heap_pct = used / mx * 100
            if heap_pct > 85:
                result["recommendations"].append({"severity": "CRITICAL", "category": "memory", "detail": f"Heap at {heap_pct:.1f}% ({format_bytes(used)}/{format_bytes(mx)}). Risk of OOM and GC thrashing.", "action": f"Increase -Xmx to at least {format_bytes(int(used * 1.3))}, or reduce memory usage."})
            elif heap_pct > 70:
                result["recommendations"].append({"severity": "WARNING", "category": "memory", "detail": f"Heap at {heap_pct:.1f}%. Getting high.", "action": "Monitor for growth trend. Consider increasing heap or reducing allocation rate."})

    if threads:
        server_threads = [t for t in threads if "server" in t.get("name", "").lower() or "region" in t.get("name", "").lower()]
        for t in server_threads:
            total = sum(t.get("times", []))
            if total == 0:
                continue
            children = t.get("children", [])
            sleep_time = 0
            for c in t.get("children", []):
                cn = c.get("className", c.get("class_name", ""))
                mn = c.get("methodName", c.get("method_name", ""))
                if _is_idle_frame(cn, mn):
                    sleep_time += sum(c.get("times", []))
            sleep_pct = pct(sleep_time, total)
            if sleep_pct < 5:
                result["recommendations"].append({"severity": "CRITICAL", "category": "overload", "detail": f"Thread '{t['name']}' has only {sleep_pct}% sleep time. Severely overloaded.", "action": "Reduce tick workload: entities, chunks, plugin tasks. Consider Folia for regional parallelism."})
            elif sleep_pct < 20:
                result["recommendations"].append({"severity": "WARNING", "category": "overload", "detail": f"Thread '{t['name']}' has {sleep_pct}% sleep time. Working very hard.", "action": "Identify hotspots with 'hotspots --exclude-sleep' and attribute with 'plugins'."})

    if gc_types:
        stw_pauses = {k: v for k, v in all_gc.items() if "pause" in k.lower() and v["avg_time"] > 0}
        for key, gc in stw_pauses.items():
            if gc["avg_time"] > 200:
                result["recommendations"].append({"severity": "CRITICAL", "category": "gc", "detail": f"GC '{gc['name']}' STW pause avg {gc['avg_time']:.1f}ms causes noticeable lag.", "action": "Tune GC flags. For G1GC use Aikar's flags. For ZGC ensure -XX:+UnlockExperimentalVMOptions is set."})
            if gc["freq"] > 5:
                result["recommendations"].append({"severity": "CRITICAL", "category": "gc", "detail": f"GC '{gc['name']}' frequency {gc['freq']:.1f}/min is very high.", "action": "Increase heap size or reduce allocation rate. High frequency = lots of short-lived objects."})

    if "ZGC" in gc_types:
        result["recommendations"].append({"severity": "INFO", "category": "gc", "detail": "ZGC detected. ZGC cycles are CONCURRENT and do NOT cause STW pauses. Only 'Pauses' matter for TPS impact.", "action": "Focus on ZGC Minor/Major Pauses, not Cycles, when assessing lag impact."})

    world_stats = pstats.get("world", pstats.get("WorldStatistics", {}))
    if world_stats:
        total_ents = world_stats.get("totalEntities", world_stats.get("total_entities", 0))
        entity_counts = world_stats.get("entityCounts", world_stats.get("entity_counts", {}))
        if total_ents > 5000:
            result["recommendations"].append({"severity": "WARNING", "category": "entities", "detail": f"{total_ents} entities across all worlds. High entity counts cause tick lag.", "action": "Reduce view-distance, use stack plugins, limit mob spawning areas, check entity_counts for top types."})
        top_entities = sorted(entity_counts.items(), key=lambda x: -x[1])[:3] if entity_counts else []
        for name, count in top_entities:
            if count > 500:
                result["recommendations"].append({"severity": "WARNING", "category": "entities", "detail": f"{count} '{name}' entities detected.", "action": f"Consider reducing {name} count or optimizing farms/spawners producing them."})

    result["priority_actions"] = sorted(
        result["recommendations"],
        key=lambda r: {"CRITICAL": 0, "WARNING": 1, "INFO": 2}.get(r.get("severity", "INFO"), 3)
    )

    return result


def _parse_simple_yaml(text):
    lines = text.splitlines()
    result = {}
    stack = [(result, 0)]
    for raw_line in lines:
        stripped = raw_line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        indent = len(stripped) - len(stripped.lstrip())
        content = stripped.strip()
        while len(stack) > 1 and stack[-1][1] >= indent:
            stack.pop()
        if content.endswith(":"):
            key = content[:-1].strip()
            new_dict = {}
            stack[-2][0][key] = new_dict if isinstance(stack[-1][0], dict) else new_dict
            stack[-1][0][key] = new_dict
            stack.append((new_dict, indent))
        elif ":" in content:
            colon_idx = content.index(":")
            key = content[:colon_idx].strip()
            val = content[colon_idx + 1:].strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            elif val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            elif val.lower() == "default":
                val = "default"
            else:
                try:
                    val = int(val) if "." not in val else float(val)
                except (ValueError, TypeError):
                    pass
            stack[-1][0][key] = val
            stack[-1] = (stack[-1][0], indent)
    return result


def _parse_json5(text):
    json5_text = text
    json5_text = re.sub(r'(?<!:)//.*$', '', json5_text, flags=re.MULTILINE)
    json5_text = re.sub(r'/\*[\s\S]*?\*/', '', json5_text)
    json5_text = re.sub(r',\s*([}\]])', r'\1', json5_text)
    json5_text = re.sub(r'(?<=[{,\[])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', json5_text)
    try:
        return json.loads(json5_text)
    except (json.JSONDecodeError, ValueError):
        return None


def _parse_server_properties(text):
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        try:
            val = int(val)
        except ValueError:
            try:
                val = float(val)
            except ValueError:
                if val.lower() == "true":
                    val = True
                elif val.lower() == "false":
                    val = False
        result[key] = val
    return result


def _get_nested(d, *keys, default=None):
    current = d
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return default
    return current


def _load_config_file(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return None
    name = os.path.basename(path).lower()
    stripped = text.strip()
    if name == "server.properties":
        return _parse_server_properties(text)
    elif name.endswith(".json5") or name.endswith(".json5.yml") or "json5" in name:
        parsed = _parse_json5(text)
        if parsed:
            return parsed
        return _parse_simple_yaml(text)
    elif stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            parsed = _parse_json5(text)
            if parsed:
                return parsed
            return _parse_simple_yaml(text)
    else:
        yaml_result = _parse_simple_yaml(text)
        if yaml_result:
            return yaml_result
        parsed = _parse_json5(text)
        if parsed:
            return parsed
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None


def _deep_merge(base, override):
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


CFG_SAFE_VALUES = {
    "hopper-transfer": (8, [1], "NEVER set to 1 — causes massive hopper lag and breaks all hopper timing. Keep at 8."),
    "hopper-amount": (1, [], "Keep at 1. Changing alters game economy and breaks hopper systems."),
    "max-entity-collisions": (8, list(range(0, 3)), "Must be >= 3. Below 3 breaks minecarts, boats, and entity interactions."),
}

CFG_DEPENDENCY_RULES = [
    {
        "check": lambda c: _get_nested(c, "spigot", "world-settings", "default", "mob-spawn-range", default=None),
        "depends_on": "simulation-distance",
        "rule": "mob-spawn-range must be <= simulation-distance - 1",
        "validate": lambda c: (_get_nested(c, "spigot", "world-settings", "default", "mob-spawn-range", default=8) or 8) <= ((_get_nested(c, "server_properties", "simulation-distance", default=10) or 10) - 1),
        "fix": "Set mob-spawn-range to simulation-distance - 1 or lower",
    },
    {
        "check": lambda c: _get_nested(c, "spigot", "world-settings", "default", "mob-spawn-range", default=None),
        "rule": "mob-spawn-range must be >= 3",
        "validate": lambda c: (_get_nested(c, "spigot", "world-settings", "default", "mob-spawn-range", default=8) or 8) >= 3,
        "fix": "Set mob-spawn-range to at least 3",
    },
    {
        "check": lambda c: _get_nested(c, "server_properties", "view-distance", default=None),
        "depends_on": "simulation-distance",
        "rule": "view-distance must be >= simulation-distance",
        "validate": lambda c: (_get_nested(c, "server_properties", "view-distance", default=10) or 10) >= (_get_nested(c, "server_properties", "simulation-distance", default=10) or 10),
        "fix": "Set view-distance >= simulation-distance",
    },
    {
        "check": lambda c: True,
        "rule": "bukkit spawn-limits must match mob-spawn-range for desired density",
        "validate": None,
        "fix": "When lowering spawn-limits, also lower mob-spawn-range proportionally. See spawn-limit cheat sheet in optimization guide.",
    },
]

GAMEMODE_PLUGIN_KEYWORDS = {
    "bedwars": {"bedwars", "bed_war", "bedwarsrel", "bedwar", "bw1058", "bw2023", "bw-", "bedwars1058"},
    "skyblock": {"skyblock", "a skyblock", "askyblock", " SuperiorSkyblock", "superiorskyblock", "bskyblock", "fabledskyblock", "island", "islands"},
    "skywars": {"skywars", "sky_war", "skywarsrel"},
    "lobby": {"lobby", "hub", "bungeecordhub", "lobbybalancer", "compassnav", "bungeecord hub", "multiverse-portals"},
    "factions": {"factions", "factionswars", "kingdoms", "towny", "sabrefactions"},
    "creative": {"creative", "plotme", "plotsquared", "worldedit", "fastasyncworldedit"},
    "modded": {"forge", "fabric", "neoforge", "modloader"},
}


def _detect_gamemode(data, meta, platform):
    plugins_raw = meta.get("sources", {})
    plugin_names = set()
    if isinstance(plugins_raw, dict):
        for pkg, info in plugins_raw.items():
            if isinstance(info, dict):
                name = info.get("name", "").lower()
                if name:
                    plugin_names.add(name)
                    desc = info.get("description", "").lower()
                    if desc:
                        plugin_names.update(desc.split())
            elif isinstance(info, str):
                plugin_names.add(info.lower())
    platform_name = platform.get("name", "").lower()
    if any(kw in platform_name for kw in ("forge", "fabric", "neoforge")):
        return "modded"
    scores = {gm: 0 for gm in GAMEMODE_PLUGIN_KEYWORDS}
    for gamemode, keywords in GAMEMODE_PLUGIN_KEYWORDS.items():
        for kw in keywords:
            for pname in plugin_names:
                if kw in pname:
                    scores[gamemode] = scores.get(gamemode, 0) + 1
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    best_single = max(scores, key=scores.get)
    if scores[best_single] >= 1:
        return best_single
    return "unknown"


CFG_GAMEMODE_RULES = {
    "smp": {
        "name": "SMP / Survival",
        "never_disable": ["doMobSpawning", "doDaylightCycle"],
        "never_change": {"hopper-transfer": 8, "max-entity-collisions": {"min": 3}, "simulation-distance": {"min": 4}},
        "safe_ranges": {
            "view-distance": (5, 8),
            "simulation-distance": (4, 6),
            "spawn-limits.monsters": (20, 70),
            "merge-radius.item": (2.5, 4.5),
        },
        "warnings": {"simulation-distance < 4": "Farms break. Mobs won't spawn correctly.", "tick-inactive-villagers: false": "Iron golem farms and trading halls break."},
    },
    "lobby": {
        "name": "Lobby / Hub",
        "never_disable": [],
        "never_change": {"hopper-transfer": 8},
        "safe_ranges": {
            "view-distance": (3, 5),
            "simulation-distance": (0, 4),
            "spawn-limits.monsters": (0, 0),
            "merge-radius.item": (5.0, 20.0),
        },
        "warnings": {},
    },
    "bedwars": {
        "name": "Bedwars / Skywars",
        "never_disable": [],
        "never_change": {"hopper-transfer": 8, "max-entity-collisions": {"min": 4}, "simulation-distance": {"min": 4}},
        "safe_ranges": {
            "view-distance": (4, 6),
            "simulation-distance": (4, 6),
            "merge-radius.item": (2.5, 3.5),
            "max-entity-collisions": (4, 8),
        },
        "warnings": {"merge-radius.item > 5": "Resources merge mid-air at generators. Breaks game feel.", "max-entity-collisions < 4": "TNT knockback breaks. Entity interactions fail."},
    },
    "skyblock": {
        "name": "Skyblock",
        "never_disable": [],
        "never_change": {"hopper-transfer": 8, "simulation-distance": {"min": 4}},
        "safe_ranges": {
            "view-distance": (4, 5),
            "simulation-distance": (4, 4),
            "merge-radius.item": (3.5, 4.5),
            "merge-radius.exp": (5.0, 6.0),
        },
        "warnings": {"hopper-transfer != 8": "Skyblock REQUIRES hoppers. Any change breaks farm timing.", "merge-radius > 5": "Farm items teleport together, breaking collection systems."},
    },
    "factions": {
        "name": "Factions / PvP",
        "never_disable": ["doMobSpawning"],
        "never_change": {"hopper-transfer": 8, "max-entity-collisions": {"min": 3}, "entity-tracking-range.players": {"min": 48}, "arrow-despawn-rate": {"min": 100}},
        "safe_ranges": {
            "view-distance": (5, 7),
            "simulation-distance": (4, 6),
            "entity-tracking-range.players": (48, 128),
        },
        "warnings": {"entity-tracking-range.players < 48": "Players become invisible at distance. PvP-breaking."},
    },
    "creative": {
        "name": "Creative / Building",
        "never_disable": [],
        "never_change": {"hopper-transfer": 8},
        "safe_ranges": {
            "view-distance": (7, 12),
            "simulation-distance": (0, 4),
            "spawn-limits.monsters": (0, 0),
        },
        "warnings": {"view-distance too low": "Builders can't see their creations."},
    },
    "modded": {
        "name": "Modded (Fabric/Forge)",
        "never_disable": ["doMobSpawning"],
        "never_change": {"hopper-transfer": 8, "simulation-distance": {"min": 4}},
        "safe_ranges": {
            "view-distance": (4, 6),
            "simulation-distance": (4, 4),
        },
        "warnings": {"low entity-activation-range": "Many mods bypass activation range. Some hard-crash if entities aren't ticked.", "low spawn-limits": "Mod entities count toward caps. Too low prevents mod mobs from spawning."},
    },
    "unknown": {
        "name": "Unknown (Conservative Defaults)",
        "never_disable": [],
        "never_change": {"hopper-transfer": 8, "max-entity-collisions": {"min": 3}, "simulation-distance": {"min": 4}},
        "safe_ranges": {
            "view-distance": (4, 7),
            "simulation-distance": (4, 6),
        },
        "warnings": {},
    },
}


def _analyze_configs(configs, gamemode, platform):
    findings = []
    sp = configs.get("server_properties", {})
    spigot = configs.get("spigot", {})
    bukkit = configs.get("bukkit", {})
    paper_global = configs.get("paper_global", {})
    paper_world = configs.get("paper_world", {})
    is_paper = platform in ("paper", "folia", "canvas")
    gamemode_rules = CFG_GAMEMODE_RULES.get(gamemode, CFG_GAMEMODE_RULES["unknown"])
    is_unknown_gamemode = (gamemode == "unknown")

    view_dist = _get_nested(sp, "view-distance", default=10)
    sim_dist = _get_nested(sp, "simulation-distance", default=10)
    online_mode = _get_nested(sp, "online-mode", default=True)

    if view_dist and sim_dist:
        if view_dist < sim_dist:
            findings.append({"severity": "CRITICAL", "category": "config_dependency", "setting": "view-distance < simulation-distance", "current": f"view-distance={view_dist}, simulation-distance={sim_dist}", "detail": "view-distance must be >= simulation-distance. Rendering breaks if view is smaller than tick distance.", "action": f"Set view-distance >= {sim_dist}"})
        if sim_dist < 4 and gamemode not in ("lobby", "creative"):
            gm_label = gamemode_rules['name'] if not is_unknown_gamemode else "servers with gameplay"
            findings.append({"severity": "CRITICAL", "category": "gameplay_break", "setting": "simulation-distance", "current": str(sim_dist), "detail": f"simulation-distance of {sim_dist} breaks mob spawning, farms, and vanilla mechanics for {gm_label}.", "action": "Set simulation-distance to at least 4 for any world with gameplay."})

    if online_mode is False and not is_paper:
        findings.append({"severity": "WARNING", "category": "security", "setting": "online-mode=false", "current": "false", "detail": "online-mode is false without a proxy. Anyone can join with any username.", "action": "Set online-mode=true unless using BungeeCord/Velocity with forwarding."})

    mob_spawn_range = _get_nested(spigot, "world-settings", "default", "mob-spawn-range", default=8)
    if mob_spawn_range and sim_dist:
        if mob_spawn_range > (sim_dist - 1):
            findings.append({"severity": "WARNING", "category": "config_dependency", "setting": "mob-spawn-range > simulation-distance - 1", "current": f"mob-spawn-range={mob_spawn_range}, simulation-distance={sim_dist}", "detail": "Mobs attempt to spawn outside simulation distance, wasting spawn cycles and reducing density.", "action": f"Set mob-spawn-range to {sim_dist - 1} or lower"})
        if mob_spawn_range < 3:
            findings.append({"severity": "WARNING", "category": "config_dependency", "setting": "mob-spawn-range too low", "current": str(mob_spawn_range), "detail": "mob-spawn-range below 3 drastically reduces spawnable area. Mobs cannot spawn within 24 blocks of players.", "action": "Set mob-spawn-range to at least 3"})

    hopper_transfer = _get_nested(spigot, "world-settings", "default", "hopper-transfer", default=None)
    ticks_hopper = _get_nested(spigot, "world-settings", "default", "ticks-per", "hopper-transfer", default=None)
    hopper_val = hopper_transfer or ticks_hopper
    if hopper_val is not None and hopper_val != 8:
        if hopper_val == 1:
            findings.append({"severity": "CRITICAL", "category": "bug_config", "setting": "hopper-transfer", "current": str(hopper_val), "detail": "hopper-transfer=1 makes hoppers process every tick (8x normal). This is the #1 cause of hopper lag on servers. It also breaks item sorters and redstone timing.", "action": "Set hopper-transfer to 8 (default). This is a NEVER-CHANGE value."})
        elif hopper_val > 8:
            findings.append({"severity": "WARNING", "category": "bug_config", "setting": "hopper-transfer", "current": str(hopper_val), "detail": f"hopper-transfer={hopper_val} makes hoppers slower than vanilla. Item sorters and farm timing break.", "action": "Set hopper-transfer to 8 (default)."})

    max_entity_collisions = _get_nested(spigot, "world-settings", "default", "max-entity-collisions", default=None)
    if max_entity_collisions is not None and max_entity_collisions < 3:
        findings.append({"severity": "CRITICAL", "category": "bug_config", "setting": "max-entity-collisions", "current": str(max_entity_collisions), "detail": f"max-entity-collisions={max_entity_collisions} is below 3. Minecarts won't link, boats break, entity interactions fail.", "action": "Set max-entity-collisions to at least 3. Use 4-8 for servers with entity interaction needs (PvP, Bedwars)."})

    merge_item = _get_nested(spigot, "world-settings", "default", "merge-radius", "item", default=None)
    if merge_item is not None:
        if not is_unknown_gamemode and gamemode in ("bedwars", "skyblock") and merge_item > 3.5:
            findings.append({"severity": "WARNING", "category": "gamemode_break", "setting": "merge-radius.item", "current": str(merge_item), "detail": f"merge-radius.item={merge_item} is too high for {gamemode_rules['name']}. Items merge mid-air at generators/farms, breaking game feel.", "action": f"Set merge-radius.item to 2.5-3.5 for {gamemode_rules['name']}"})
        elif not is_unknown_gamemode and merge_item > 5.0 and gamemode not in ("lobby", "creative"):
            findings.append({"severity": "WARNING", "category": "bug_config", "setting": "merge-radius.item", "current": str(merge_item), "detail": f"merge-radius.item={merge_item} causes items to teleport together mid-air. Farm collection systems break.", "action": "Set merge-radius.item to 3.0-4.0 for SMP, 2.5-3.5 for PvP/Skyblock."})

    nerf_spawner = _get_nested(spigot, "world-settings", "default", "nerf-spawner-mobs", default=None)
    if nerf_spawner is True and gamemode in ("smp", "skyblock") and not is_unknown_gamemode:
        findings.append({"severity": "WARNING", "category": "gameplay_break", "setting": "nerf-spawner-mobs", "current": "true", "detail": f"nerf-spawner-mobs=true removes ALL AI from spawner mobs. Any farm using spawner mob AI breaks for {gamemode_rules['name']}.", "action": "Set to false, or if needed set spawner-nerfed-mobs-should-jump=true in paper-world."})

    tick_inactive_villagers = None
    if is_paper:
        tick_inactive_villagers = _get_nested(paper_global, "entities", "activation-range", "tick-inactive-villagers", default=None)
        if tick_inactive_villagers is False and gamemode in ("smp", "skyblock") and not is_unknown_gamemode:
            findings.append({"severity": "WARNING", "category": "gameplay_break", "setting": "tick-inactive-villagers", "current": "false", "detail": f"tick-inactive-villagers=false breaks iron golem farms and villager restocking when no player is nearby. Critical for {gamemode_rules['name']}.", "action": "Set to true for SMP/Skyblock, or use VillagerLobotimizer plugin as alternative."})

    entity_act = {}
    act_section = _get_nested(spigot, "world-settings", "default", "entity-activation-range", default={})
    if act_section:
        entity_act = act_section
    if is_paper:
        paper_act = _get_nested(paper_global, "entities", "activation-range", default={})
        if paper_act:
            entity_act = _deep_merge(entity_act, paper_act)

    if entity_act and sim_dist:
        max_activation = (sim_dist - 1) * 16
        for category in ("animals", "monsters", "villagers", "flying-monsters", "raiders"):
            val = entity_act.get(category)
            if val is not None and val > max_activation:
                findings.append({"severity": "WARNING", "category": "config_dependency", "setting": f"entity-activation-range.{category}", "current": str(val), "detail": f"entity-activation-range.{category}={val} exceeds (simulation-distance-1)*16={max_activation}. Entities beyond sim distance won't tick anyway.", "action": f"Set to {max_activation} or lower."})

    spawn_limits_monsters = _get_nested(bukkit, "spawn-limits", "monsters", default=None)
    if spawn_limits_monsters is not None and spawn_limits_monsters > 50 and gamemode in ("smp",) and not is_unknown_gamemode:
        findings.append({"severity": "LOW", "category": "optimization", "setting": "spawn-limits.monsters", "current": str(spawn_limits_monsters), "detail": f"spawn-limits.monsters={spawn_limits_monsters} is high for SMP. High spawn counts = more entity CPU.", "action": "Consider 30-50 for balanced performance, adjusting mob-spawn-range proportionally."})

    entity_tracking_players = _get_nested(spigot, "world-settings", "default", "entity-tracking-range", "players", default=None)
    if is_paper:
        paper_track_players = _get_nested(paper_global, "entities", "tracking-range", "players", default=None)
        if paper_track_players:
            entity_tracking_players = paper_track_players
    if entity_tracking_players is not None and entity_tracking_players < 48 and gamemode in ("factions",) and not is_unknown_gamemode:
        findings.append({"severity": "CRITICAL", "category": "gamemode_break", "setting": "entity-tracking-range.players", "current": str(entity_tracking_players), "detail": f"entity-tracking-range.players={entity_tracking_players} is too low for {gamemode_rules['name']}. Players become invisible at distance in PvP.", "action": "Set to at least 48 for PvP servers."})

    arrow_despawn = _get_nested(spigot, "world-settings", "default", "arrow-despawn-rate", default=None)
    if arrow_despawn is not None and arrow_despawn < 100 and gamemode in ("factions", "bedwars") and not is_unknown_gamemode:
        findings.append({"severity": "WARNING", "category": "gamemode_break", "setting": "arrow-despawn-rate", "current": str(arrow_despawn), "detail": f"arrow-despawn-rate={arrow_despawn} is below 100. Arrows vanish during bow combat in {gamemode_rules['name']}.", "action": "Set to 100-300 for PvP servers."})

    if is_paper:
        despawn_hard_h = _get_nested(paper_world, "entities", "spawning", "despawn-ranges", "monster", "hard", "horizontal", default=None)
        if despawn_hard_h is not None and sim_dist:
            expected = (sim_dist - 1) * 16
            if despawn_hard_h < 36:
                findings.append({"severity": "WARNING", "category": "bug_config", "setting": "despawn-ranges.monster.hard.horizontal", "current": str(despawn_hard_h), "detail": f"despawn-ranges.hard.horizontal={despawn_hard_h} is below 36. Mobs vanish while player can see them, breaking farms.", "action": f"Set to at least 36, ideally {(sim_dist - 1) * 16}"})
            elif sim_dist < 10 and despawn_hard_h != expected and despawn_hard_h > expected:
                findings.append({"severity": "INFO", "category": "optimization", "setting": "despawn-ranges.monster.hard.horizontal", "current": str(despawn_hard_h), "detail": f"With simulation-distance={sim_dist}, ideal despawn hard horizontal is {expected}.", "action": f"Set to {expected} for best mob despawn behavior."})

    prevent_moving = _get_nested(paper_world, "chunks", "prevent-moving-into-unloaded-chunks", default=None)
    if prevent_moving is False and is_paper:
        findings.append({"severity": "LOW", "category": "optimization", "setting": "prevent-moving-into-unloaded-chunks", "current": "false", "detail": "Disabling this causes sync chunk loads when players move into unloaded chunks, causing lag spikes.", "action": "Set to true (recommended)."})

    alt_despawn = _get_nested(paper_world, "entities", "spawning", "alt-item-despawn-rate", "enabled", default=None)
    if alt_despawn is False and gamemode in ("smp", "skyblock") and not is_unknown_gamemode:
        findings.append({"severity": "LOW", "category": "optimization", "setting": "alt-item-despawn-rate.enabled", "current": "false", "detail": f"alt-item-despawn-rate is disabled. Enabling it speeds up despawn of common junk items (cobblestone, netherrack) without affecting farm items.", "action": "Enable alt-item-despawn-rate and configure junk items."})

    redstone_impl = _get_nested(paper_world, "misc", "redstone-implementation", default=None)
    if redstone_impl and redstone_impl == "VANILLA" and is_paper:
        findings.append({"severity": "LOW", "category": "optimization", "setting": "redstone-implementation", "current": "VANILLA", "detail": "ALTERNATE_CURRENT is more efficient. Behavior differs slightly from Vanilla.", "action": "Set to ALTERNATE_CURRENT for better performance. Test redstone builds first."})

    epcl_item = _get_nested(paper_world, "entities", "spawning", "entity-per-chunk-save-limit", "item", default=None)
    if epcl_item is None and is_paper:
        findings.append({"severity": "WARNING", "category": "security", "setting": "entity-per-chunk-save-limit.item", "current": "not set", "detail": "entity-per-chunk-save-limit is not set for items. Players can crash the server by loading chunks full of items.", "action": "Set entity-per-chunk-save-limit.item to 40-100."})

    canvas_config = configs.get("canvas_config", {})
    if canvas_config and "canvas" in platform:
        async_chunks = _get_nested(canvas_config, "performance", "enable-async-chunks", default=None)
        if async_chunks is False:
            findings.append({"severity": "LOW", "category": "optimization", "setting": "canvas enable-async-chunks", "current": "false", "detail": "Async chunk loading is disabled on Canvas. Enabling it distributes chunk loading across threads.", "action": "Set enable-async-chunks to true."})
        async_mobs = _get_nested(canvas_config, "performance", "enable-async-mobs", default=None)
        if async_mobs is False:
            findings.append({"severity": "LOW", "category": "optimization", "setting": "canvas enable-async-mobs", "current": "false", "detail": "Async mob spawning is disabled on Canvas. Enabling it distributes mob spawn calculations.", "action": "Set enable-async-mobs to true."})

    purpur_config = configs.get("purpur_config", {})
    if purpur_config:
        purpur_anti_xray = _get_nested(purpur_config, "settings", "anti-xray", default=None)
        if purpur_anti_xray is not None and is_paper:
            findings.append({"severity": "INFO", "category": "optimization", "setting": "purpur anti-xray", "current": str(purpur_anti_xray), "detail": "Purpur has its own anti-xray settings. Paper also has anti-xray. Using both may cause conflicts.", "action": "Use Paper's anti-xray (paper-world.yml) or Purpur's, not both."})

    velocity_config = configs.get("velocity_config", {})
    if velocity_config:
        vel_online_mode = _get_nested(velocity_config, "online-mode", default=None)
        if vel_online_mode is False:
            findings.append({"severity": "WARNING", "category": "security", "setting": "velocity online-mode", "current": "false", "detail": "Velocity online-mode is false. Players can join with any username unless you have a forwarding secret configured.", "action": "Set online-mode to true, or ensure forwarding-secret is properly configured."})
        vel_compression = _get_nested(velocity_config, "advanced", "compression-threshold", default=None)
        if vel_compression is not None and vel_compression > 512:
            findings.append({"severity": "LOW", "category": "optimization", "setting": "velocity compression-threshold", "current": str(vel_compression), "detail": f"Velocity compression threshold of {vel_compression} may cause noticeable lag on slow connections.", "action": "Consider a threshold of 256-512."})

    return findings


def cmd_check_config(args):
    data, src = load_data(args.source)
    if not data:
        return {"error": "Could not load data from source"}

    meta = get_metadata(data)
    platform = get_platform_meta(meta)
    configs = meta.get("serverConfigurations", meta.get("server_configurations", {}))
    jvm_flags_str = configs.get("jvm_args", configs.get("flags", ""))

    sstats = get_system_stats(meta)
    java_info = sstats.get("java", {})
    if not jvm_flags_str and java_info.get("flags"):
        jvm_flags_str = java_info["flags"]
    if not jvm_flags_str and java_info.get("runtimeName"):
        pass
    if not jvm_flags_str:
        jvm_flags_str = sstats.get("jvm_flags", "")

    server_name = platform.get("name", "").lower()
    result = {
        "platform": platform,
        "jvm_analysis": {},
        "config_analysis": {},
        "parsed_configs": {},
        "recommendations": [],
    }

    config_dir = getattr(args, 'config_dir', None)
    config_files = {}
    if config_dir:
        config_dir = os.path.expanduser(config_dir)
        file_map = {
            "server_properties": ["server.properties"],
            "spigot": ["spigot.yml"],
            "bukkit": ["bukkit.yml"],
            "paper_global": ["paper-global.yml", "config/paper-global.yml"],
            "paper_world": ["paper-world.yml", "paper-world-defaults.yml", "config/paper-world-defaults.yml"],
            "paper_world_nether": ["world_nether/paper-world.yml", "world_nether/paper-world-defaults.yml"],
            "paper_world_end": ["world_the_end/paper-world.yml", "world_the_end/paper-world-defaults.yml"],
            "canvas_config": ["canvas-server.json5", "config/canvas-server.json5", "canvas-config.json5"],
            "velocity_config": ["velocity.toml", "config/velocity.toml"],
            "bungee_config": ["config.yml", "BungeeCord/config.yml"],
            "pufferfish_config": ["pufferfish.yml", "config/pufferfish.yml"],
            "purpur_config": ["purpur.yml", "config/purpur.yml"],
        }
        for key, names in file_map.items():
            for name in names:
                fpath = os.path.join(config_dir, name)
                if os.path.isfile(fpath):
                    parsed = _load_config_file(fpath)
                    if parsed:
                        config_files[key] = parsed
                        break

    sp_path = getattr(args, 'server_properties', None)
    spigot_path = getattr(args, 'spigot_yml', None)
    bukkit_path = getattr(args, 'bukkit_yml', None)
    pg_path = getattr(args, 'paper_global_yml', None)
    pw_path = getattr(args, 'paper_world_yml', None)
    canvas_path = getattr(args, 'canvas_config', None)
    velocity_path = getattr(args, 'velocity_config', None)
    pufferfish_path = getattr(args, 'pufferfish_config', None)
    purpur_path = getattr(args, 'purpur_config', None)

    if sp_path and os.path.isfile(sp_path):
        parsed = _load_config_file(sp_path)
        if parsed:
            config_files["server_properties"] = parsed
    if spigot_path and os.path.isfile(spigot_path):
        parsed = _load_config_file(spigot_path)
        if parsed:
            config_files["spigot"] = parsed
    if bukkit_path and os.path.isfile(bukkit_path):
        parsed = _load_config_file(bukkit_path)
        if parsed:
            config_files["bukkit"] = parsed
    if pg_path and os.path.isfile(pg_path):
        parsed = _load_config_file(pg_path)
        if parsed:
            config_files["paper_global"] = parsed
    if pw_path and os.path.isfile(pw_path):
        parsed = _load_config_file(pw_path)
        if parsed:
            config_files["paper_world"] = parsed
    if canvas_path and os.path.isfile(canvas_path):
        parsed = _load_config_file(canvas_path)
        if parsed:
            config_files["canvas_config"] = parsed
    if velocity_path and os.path.isfile(velocity_path):
        parsed = _load_config_file(velocity_path)
        if parsed:
            config_files["velocity_config"] = parsed
    if pufferfish_path and os.path.isfile(pufferfish_path):
        parsed = _load_config_file(pufferfish_path)
        if parsed:
            config_files["pufferfish_config"] = parsed
    if purpur_path and os.path.isfile(purpur_path):
        parsed = _load_config_file(purpur_path)
        if parsed:
            config_files["purpur_config"] = parsed

    for key in ("server_properties", "server.properties", "spigot", "spigot.yml", "bukkit", "bukkit.yml", "paper_global", "paper-global.yml", "paper_world", "paper-world.yml", "paper-world-defaults.yml", "canvas_config", "canvas-server.json5", "velocity_config", "velocity.toml", "pufferfish_config", "pufferfish.yml", "purpur_config", "purpur.yml"):
        cfg_val = configs.get(key)
        if cfg_val and key not in config_files and key.replace(".", "_").replace("-", "_") not in config_files:
            try:
                if isinstance(cfg_val, str) and cfg_val.strip().startswith(("{", "[")):
                    try:
                        parsed_val = json.loads(cfg_val)
                    except (json.JSONDecodeError, ValueError):
                        parsed_val = _parse_json5(cfg_val)
                elif isinstance(cfg_val, str):
                    if key in ("server.properties", "server_properties"):
                        parsed_val = _parse_server_properties(cfg_val) if "=" in cfg_val else None
                    else:
                        parsed_val = _parse_simple_yaml(cfg_val)
                elif isinstance(cfg_val, dict):
                    parsed_val = cfg_val
                else:
                    parsed_val = None
                if parsed_val:
                    normalized_key = key.replace(".", "_").replace("-", "_").replace("/", "_").rstrip("_")
                    if "server_properties" in normalized_key or normalized_key == "server_properties":
                        config_files.setdefault("server_properties", parsed_val)
                    elif normalized_key in ("spigot", "spigot_yml"):
                        config_files.setdefault("spigot", parsed_val)
                    elif normalized_key in ("bukkit", "bukkit_yml"):
                        config_files.setdefault("bukkit", parsed_val)
                    elif normalized_key in ("paper_global", "paper_global_yml"):
                        config_files.setdefault("paper_global", parsed_val)
                    elif normalized_key in ("paper_world", "paper_world_yml", "paper_world_defaults_yml"):
                        config_files.setdefault("paper_world", parsed_val)
                    elif normalized_key in ("canvas_config", "canvas_server_json5"):
                        config_files.setdefault("canvas_config", parsed_val)
                    elif normalized_key in ("velocity_config", "velocity_toml"):
                        config_files.setdefault("velocity_config", parsed_val)
                    elif normalized_key in ("pufferfish_config", "pufferfish_yml"):
                        config_files.setdefault("pufferfish_config", parsed_val)
                    elif normalized_key in ("purpur_config", "purpur_yml"):
                        config_files.setdefault("purpur_config", parsed_val)
                    else:
                        config_files[normalized_key] = parsed_val
            except (json.JSONDecodeError, ValueError):
                pass

    for raw_key, raw_val in configs.items():
        if raw_val and raw_key not in configs:
            continue
        key = raw_key
        val = raw_val
        if key in config_files or key.replace(".", "_").replace("-", "_").replace("/", "_").rstrip("_") in config_files:
            continue
        try:
            if isinstance(val, str) and val.strip().startswith(("{", "[")):
                try:
                    parsed_val = json.loads(val)
                except (json.JSONDecodeError, ValueError):
                    parsed_val = _parse_json5(val)
            elif isinstance(val, str):
                parsed_val = _parse_simple_yaml(val)
            elif isinstance(val, dict):
                parsed_val = val
            else:
                continue
            if not parsed_val:
                continue
            normalized = key.replace(".", "_").replace("-", "_").replace("/", "_").rstrip("_")
            if "server_properties" in normalized or normalized == "server_properties":
                config_files.setdefault("server_properties", parsed_val)
            elif normalized in ("spigot", "spigot_yml"):
                config_files.setdefault("spigot", parsed_val)
            elif normalized in ("bukkit", "bukkit_yml"):
                config_files.setdefault("bukkit", parsed_val)
            elif "paper_global" in normalized or "paper_global_yml" in normalized:
                config_files.setdefault("paper_global", parsed_val)
            elif "paper_world" in normalized or "paper_world_defaults" in normalized:
                config_files.setdefault("paper_world", parsed_val)
            elif "canvas" in normalized:
                config_files.setdefault("canvas_config", parsed_val)
            elif "velocity" in normalized:
                config_files.setdefault("velocity_config", parsed_val)
            elif "pufferfish" in normalized:
                config_files.setdefault("pufferfish_config", parsed_val)
            elif "purpur" in normalized:
                config_files.setdefault("purpur_config", parsed_val)
            else:
                config_files[key] = parsed_val
        except (json.JSONDecodeError, ValueError):
            pass

    result["parsed_configs"] = config_files

    gamemode_arg = getattr(args, 'gamemode', None)
    if gamemode_arg:
        gamemode = gamemode_arg
        result["gamemode"] = gamemode
        result["gamemode_source"] = "user_specified"
    else:
        gamemode = _detect_gamemode(data, meta, platform)
        result["gamemode"] = gamemode
        result["gamemode_source"] = "auto_detected"
    platform_type = "paper" if "paper" in server_name else ("folia" if "folia" in server_name else ("canvas" if "canvas" in server_name else ("spigot" if "spigot" in server_name else "bukkit")))

    if config_files:
        config_findings = _analyze_configs(config_files, gamemode, platform_type)
        result["config_analysis"] = {
            "files_parsed": list(config_files.keys()),
            "findings_count": len(config_findings),
        }
        result["recommendations"].extend(config_findings)

    if not jvm_flags_str:
        result["jvm_analysis"] = {"status": "NO_DATA", "detail": "JVM flags not found in profile. Provide --config-dir or check startup script."}
    else:
        flags = jvm_flags_str if isinstance(jvm_flags_str, list) else jvm_flags_str.split()
        flags_str = " ".join(flags) if isinstance(flags, list) else jvm_flags_str

        def has_flag(pattern):
            return bool(re.search(pattern, flags_str, re.IGNORECASE))

        result["jvm_analysis"]["raw_flags"] = flags_str

        xmx_match = re.search(r"-Xmx(\d+)([gGmMkK]?)", flags_str)
        xms_match = re.search(r"-Xms(\d+)([gGmMkK]?)", flags_str)
        if xmx_match:
            xmx_val = int(xmx_match.group(1))
            xmx_unit = xmx_match.group(2).upper() or "M"
            result["jvm_analysis"]["heap_max"] = f"{xmx_val}{xmx_unit}"
        if xms_match:
            xms_val = int(xms_match.group(1))
            xms_unit = xms_match.group(2).upper() or "M"
            result["jvm_analysis"]["heap_init"] = f"{xms_val}{xms_unit}"
        if xmx_match and xms_match:
            if xms_val != xmx_val or xms_match.group(2).upper() != xmx_match.group(2).upper():
                result["recommendations"].append({"severity": "WARNING", "category": "jvm", "detail": "-Xms and -Xmx should be equal to prevent heap fragmentation.", "action": f"Set both to -Xms{xmx_val}{xmx_unit} -Xmx{xmx_val}{xmx_unit}"})

        gc_detected = None
        if has_flag(r"UseZGC|ZGarbageCollector"):
            gc_detected = "ZGC"
        elif has_flag(r"UseG1GC"):
            gc_detected = "G1GC"
        elif has_flag(r"UseParallelGC|UseParallelOldGC"):
            gc_detected = "Parallel"
        elif has_flag(r"UseConcMarkSweepGC|UseCMS"):
            gc_detected = "CMS"
        result["jvm_analysis"]["detected_gc"] = gc_detected

        if gc_detected == "Parallel":
            result["recommendations"].append({"severity": "CRITICAL", "category": "gc", "detail": "Parallel GC causes STW pauses. Switch to G1GC (Aikar's flags) for Minecraft.", "action": "Use G1GC or ZGC instead. See jvm-gc-tuning.md reference."})
        elif gc_detected == "CMS":
            result["recommendations"].append({"severity": "CRITICAL", "category": "gc", "detail": "CMS GC is deprecated and unsuitable for Minecraft. Switch to G1GC or ZGC.", "action": "Use G1GC with Aikar's flags or ZGC for large heaps (>30GB)."})

        if gc_detected == "G1GC":
            aikar_flags = {
                "G1NewSizePercent": "40",
                "G1ReservePercent": "20",
                "MaxGCPauseMillis": "200",
                "G1HeapRegionSize": None,
                "MaxTenuringThreshold": "1",
                "SurvivorRatio": "32",
                "G1MixedGCCountTarget": "4",
                "G1MixedGCLiveThresholdPercent": "90",
                "G1RSetUpdatingPauseTimePercent": "5",
            }
            missing = []
            for flag, expected in aikar_flags.items():
                if not has_flag(flag):
                    missing.append(flag)
            if missing:
                result["recommendations"].append({"severity": "WARNING", "category": "gc_tuning", "detail": f"Missing Aikar's G1GC flags: {', '.join(missing)}", "action": "Add these flags for optimal G1GC performance. See jvm-gc-tuning.md reference."})

            if xmx_match:
                heap_gb = xmx_val if xmx_match.group(2).upper() == "G" else xmx_val / 1024
                if heap_gb >= 12 and not has_flag(r"G1HeapRegionSize"):
                    result["recommendations"].append({"severity": "CRITICAL", "category": "gc_tuning", "detail": f"Missing -XX:G1HeapRegionSize for {heap_gb}GB heap. Critical for preventing humongous objects.", "action": f"Set -XX:G1HeapRegionSize={8 if heap_gb < 32 else 16}M"})

        if gc_detected == "ZGC":
            zgc_flags = ["ZUncommit", "AlwaysPreTouch", "ParallelRefProcEnabled", "UseLargePages"]
            for flag in zgc_flags:
                neg_flag = f"-XX:-{flag}"
                pos_flag = f"-XX:+{flag}"
                if pos_flag in flags_str:
                    pass
                elif neg_flag in flags_str and flag == "ZUncommit":
                    result["recommendations"].append({"severity": "INFO", "category": "zgc", "detail": "ZUncommit is disabled, which is recommended for Minecraft.", "action": "Keep -XX:-ZUncommit to prevent heap shrinking."})
            if not has_flag(r"AlwaysPreTouch"):
                result["recommendations"].append({"severity": "WARNING", "category": "jvm", "detail": "Missing -XX:+AlwaysPreTouch. Pre-touching heap pages improves startup consistency.", "action": "Add -XX:+AlwaysPreTouch"})
            if not has_flag(r"ParallelRefProcEnabled"):
                result["recommendations"].append({"severity": "INFO", "category": "jvm", "detail": "Consider -XX:+ParallelRefProcEnabled for parallel reference processing.", "action": "Add -XX:+ParallelRefProcEnabled"})

        if not has_flag(r"DisableExplicitGC"):
            result["recommendations"].append({"severity": "WARNING", "category": "jvm", "detail": "Missing -XX:+DisableExplicitGC. Plugins can trigger full GC causing lag spikes.", "action": "Add -XX:+DisableExplicitGC unless you specifically need System.gc() calls."})

        if has_flag(r"UseStringDeduplication") and gc_detected == "ZGC":
            result["recommendations"].append({"severity": "INFO", "category": "jvm", "detail": "String deduplication enabled with ZGC - this reduces memory for duplicate strings.", "action": "Keep this flag for memory optimization."})

        if has_flag(r"UseNUMA"):
            result["recommendations"].append({"severity": "INFO", "category": "jvm", "detail": "NUMA awareness enabled. Good for multi-socket systems.", "action": "Keep -XX:+UseNUMA if on multi-socket hardware."})

        if not has_flag(r"MaxInlineLevel") and "velocity" in server_name:
            result["recommendations"].append({"severity": "INFO", "category": "jvm", "detail": "For Velocity proxy, consider -XX:MaxInlineLevel=15 for better JIT optimization.", "action": "Add -XX:MaxInlineLevel=15 to startup flags."})

        if has_flag(r"ActiveProcessorCount"):
            apc_match = re.search(r"-XX:ActiveProcessorCount=(\d+)", flags_str)
            if apc_match:
                apc_val = int(apc_match.group(1))
                cpu_threads = sstats.get("cpu", {}).get("threads", 0) if sstats.get("cpu", {}).get("threads") else 0
                result["jvm_analysis"]["active_processor_count"] = apc_val
                if cpu_threads and apc_val != cpu_threads:
                    result["recommendations"].append({"severity": "WARNING", "category": "jvm", "detail": f"ActiveProcessorCount={apc_val} overrides detected CPU thread count ({cpu_threads}). This limits JVM thread pools to {apc_val} threads.", "action": f"Set ActiveProcessorCount to match your actual core count ({cpu_threads}) unless you are intentionally capping for shared hosting."})
                elif not cpu_threads:
                    result["recommendations"].append({"severity": "INFO", "category": "jvm", "detail": f"ActiveProcessorCount={apc_val} is set. Verify this matches your actual physical/vCPU core count for optimal thread pool sizing.", "action": "Ensure ActiveProcessorCount matches your CPU core count."})

        if has_flag(r"UnlockDiagnosticVMOptions"):
            result["jvm_analysis"]["unlock_diagnostic"] = True

        if has_flag(r"UnlockExperimentalVMOptions"):
            result["jvm_analysis"]["unlock_experimental"] = True

        if has_flag(r"UseAVX"):
            avx_match = re.search(r"-XX:UseAVX=(\d+)", flags_str)
            if avx_match:
                avx_val = int(avx_match.group(1))
                result["jvm_analysis"]["use_avx"] = avx_val
                if avx_val >= 3:
                    result["recommendations"].append({"severity": "LOW", "category": "jvm", "detail": f"UseAVX={avx_val} requires CPU support for AVX-{avx_val}. Older CPUs may crash with UnsupportedHardwareException.", "action": "Verify your CPU supports AVX-{avx_val}. Most modern CPUs support AVX2 (2), fewer support AVX-512 (3). Use AVX=2 for broader compatibility."})

        if has_flag(r"UseCompactObjectHeaders"):
            result["jvm_analysis"]["compact_object_headers"] = True
            if gc_detected == "G1GC":
                result["recommendations"].append({"severity": "WARNING", "category": "jvm", "detail": "UseCompactObjectHeaders is enabled with G1GC. This is an experimental flag that can reduce memory but may cause compatibility issues with some JVM versions.", "action": "Test thoroughly. Remove if you experience crashes or unexpected behavior."})

        if has_flag(r"UseTransparentHugePages"):
            result["jvm_analysis"]["transparent_huge_pages"] = True
            if "linux" not in sstats.get("os", {}).get("name", "").lower():
                result["recommendations"].append({"severity": "WARNING", "category": "jvm", "detail": "UseTransparentHugePages is enabled but the OS may not be Linux. THP behavior differs on Windows/macOS.", "action": "Remove UseTransparentHugePages if not on Linux. On Linux, ensure system THP is configured (madvise mode recommended)."})

        if has_flag(r"AlwaysPreTouchStacks"):
            result["jvm_analysis"]["always_pretouch_stacks"] = True
            result["recommendations"].append({"severity": "INFO", "category": "jvm", "detail": "AlwaysPreTouchStacks pre-touches thread stacks at creation. Improves startup consistency but increases memory usage per thread.", "action": "Keep if startup consistency is important. Remove if memory is tight."})

        if has_flag(r"UseStringDeduplication") and gc_detected != "ZGC":
            result["recommendations"].append({"severity": "INFO", "category": "jvm", "detail": "UseStringDeduplication is enabled with " + (gc_detected or "unknown GC") + ". Most effective with G1GC. Can slightly increase GC pause times.", "action": "Keep for memory optimization. Monitor GC pause times."})

        soft_ref_match = re.search(r"-XX:SoftRefLRUPolicyMSPerMB=(\d+)", flags_str)
        if soft_ref_match:
            sru_val = int(soft_ref_match.group(1))
            result["jvm_analysis"]["soft_ref_lru"] = sru_val
            if sru_val < 1000:
                result["recommendations"].append({"severity": "WARNING", "category": "jvm", "detail": f"SoftRefLRUPolicyMSPerMB={sru_val} is very low. Soft references will be cleared aggressively, which can break caches (like LevelDB cache, plugin caches).", "action": "Set to 1000-2000 for Minecraft servers. The default is 1000."})
            elif sru_val > 10000:
                result["recommendations"].append({"severity": "LOW", "category": "jvm", "detail": f"SoftRefLRUPolicyMSPerMB={sru_val} is very high. Soft references will persist much longer, potentially causing memory pressure.", "action": "Consider 1000-2000. Current value means soft refs survive {sru_val}ms per MB of heap."})

        if has_flag(r"AlwaysActAsServerClassMachine"):
            result["jvm_analysis"]["server_class_machine"] = True

        ci_count_match = re.search(r"-XX:CICompilerCount=(\d+)", flags_str)
        if ci_count_match:
            ci_val = int(ci_count_match.group(1))
            result["jvm_analysis"]["ci_compiler_count"] = ci_val
            cpu_threads = sstats.get("cpu", {}).get("threads", 0)
            if cpu_threads and ci_val > cpu_threads:
                result["recommendations"].append({"severity": "WARNING", "category": "jvm", "detail": f"CICompilerCount={ci_val} exceeds CPU threads ({cpu_threads}). Extra compiler threads will compete for CPU without benefit.", "action": f"Set CICompilerCount to {max(2, min(8, cpu_threads // 2))} for {cpu_threads} cores."})
            elif cpu_threads and ci_val < 2:
                result["recommendations"].append({"severity": "WARNING", "category": "jvm", "detail": f"CICompilerCount={ci_val} is too low. JVM JIT compilation will be slow, causing longer warmup and lower peak performance.", "action": "Set CICompilerCount to at least 2. Recommended: 4-8 for most servers."})

        if has_flag(r"UseCriticalCompilerThreadPriority"):
            result["jvm_analysis"]["critical_compiler_thread_priority"] = True

        if has_flag(r"UseCriticalJavaThreadPriority"):
            result["jvm_analysis"]["critical_java_thread_priority"] = True
            result["recommendations"].append({"severity": "INFO", "category": "jvm", "detail": "UseCriticalJavaThreadPriority increases Java thread priority. On most Linux systems this has no effect unless you run as root.", "action": "Keep if on Windows or running as root on Linux. Otherwise it has no effect."})

        if has_flag(r"SegmentedCodeCache"):
            result["jvm_analysis"]["segmented_code_cache"] = True
            reserved_match = re.search(r"-XX:ReservedCodeCacheSize=(\d+)([gGmMkK]?)", flags_str)
            non_prof_match = re.search(r"-XX:NonProfiledCodeHeapSize=(\d+)([gGmMkK]?)", flags_str)
            prof_match = re.search(r"-XX:ProfiledCodeHeapSize=(\d+)([gGmMkK]?)", flags_str)
            if reserved_match:
                rc_val = int(reserved_match.group(1))
                rc_unit = (reserved_match.group(2) or "M").upper()
                result["jvm_analysis"]["reserved_code_cache"] = f"{rc_val}{rc_unit}"
                if rc_val > 1500 and rc_unit == "M":
                    result["recommendations"].append({"severity": "LOW", "category": "jvm", "detail": f"ReservedCodeCacheSize={rc_val}{rc_unit} is very large. This reserves {rc_val}MB of memory for JIT compiled code.", "action": "512-784MB is typically sufficient for Minecraft. Reduce unless you see 'CodeCache is full' errors."})
            if non_prof_match and reserved_match:
                np_val = int(non_prof_match.group(1))
                prof_val = int(prof_match.group(1)) if prof_match else 0
                total_segmented = np_val + prof_val
                rc_val_num = int(reserved_match.group(1))
                if total_segmented > rc_val_num * 0.9:
                    result["recommendations"].append({"severity": "WARNING", "category": "jvm", "detail": f"NonProfiledCodeHeapSize ({np_val}M) + ProfiledCodeHeapSize ({prof_val}M) = {total_segmented}M, which is close to or exceeds ReservedCodeCacheSize ({rc_val_num}M). The JVM needs ~15% headroom.", "action": f"Increase ReservedCodeCacheSize or decrease the segment sizes."})

        if has_flag(r"DontCompileHugeMethods") and "-XX:-DontCompileHugeMethods" in flags_str:
            result["jvm_analysis"]["dont_compile_huge_methods"] = False
        elif has_flag(r"DontCompileHugeMethods"):
            result["jvm_analysis"]["dont_compile_huge_methods"] = True

        inline_level = re.search(r"-XX:MaxInlineLevel=(\d+)", flags_str)
        if inline_level:
            il_val = int(inline_level.group(1))
            result["jvm_analysis"]["max_inline_level"] = il_val
            if il_val > 20:
                result["recommendations"].append({"severity": "WARNING", "category": "jvm", "detail": f"MaxInlineLevel={il_val} is above the default (9) and even above the common tuned value (20). Very high inline levels cause JIT to spend more time compiling and can increase code cache usage.", "action": "Use 15-20 for balanced performance. Values above 20 rarely help and may hurt."})

        inline_size = re.search(r"-XX:MaxInlineSize=(\d+)", flags_str)
        if inline_size:
            is_val = int(inline_size.group(1))
            result["jvm_analysis"]["max_inline_size"] = is_val
            if is_val > 300:
                result["recommendations"].append({"severity": "LOW", "category": "jvm", "detail": f"MaxInlineSize={is_val} is very high (default: 35). This allows the JIT to inline larger methods, increasing compiled code size.", "action": "Use 200-270 for tuned servers. Higher values increase code cache pressure."})

        freq_inline = re.search(r"-XX:FreqInlineSize=(\d+)", flags_str)
        if freq_inline:
            fi_val = int(freq_inline.group(1))
            result["jvm_analysis"]["freq_inline_size"] = fi_val
            if fi_val > 3000:
                result["recommendations"].append({"severity": "LOW", "category": "jvm", "detail": f"FreqInlineSize={fi_val} is very high (default: 325). This allows very hot methods to be inlined regardless of size.", "action": "Acceptable for tuned servers. Monitor code cache usage."})

        inline_small = re.search(r"-XX:InlineSmallCode=(\d+)", flags_str)
        if inline_small:
            isc_val = int(inline_small.group(1))
            result["jvm_analysis"]["inline_small_code"] = isc_val

        loop_unroll = re.search(r"-XX:LoopUnrollLimit=(\d+)", flags_str)
        if loop_unroll:
            lu_val = int(loop_unroll.group(1))
            result["jvm_analysis"]["loop_unroll_limit"] = lu_val

        autobox = re.search(r"-XX:AutoBoxCacheMax=(\d+)", flags_str)
        if autobox:
            ab_val = int(autobox.group(1))
            result["jvm_analysis"]["auto_box_cache_max"] = ab_val
            if ab_val > 20000:
                result["recommendations"].append({"severity": "LOW", "category": "jvm", "detail": f"AutoBoxCacheMax={ab_val} caches Integer values up to {ab_val}. Default is 128. High values increase memory usage slightly.", "action": "10000-20000 is reasonable for servers with heavy Integer usage. Keep if you've measured a benefit."})

        if has_flag(r"UseFMA"):
            result["jvm_analysis"]["use_fma"] = True

        if has_flag(r"UseCMoveUnconditionally"):
            result["jvm_analysis"]["use_cmove"] = True

        if has_flag(r"UseSuperWord"):
            result["jvm_analysis"]["use_superword"] = True

        if has_flag(r"UseVectorMacroLogic"):
            result["jvm_analysis"]["use_vector_macro_logic"] = True

        systemd_props = re.findall(r"-D([a-zA-Z0-9_.-]+)=(\S+)", flags_str)
        for prop_name, prop_val in systemd_props:
            if prop_name == "log4j2.formatMsgNoLookups":
                result["jvm_analysis"]["log4j_fix"] = True
            elif prop_name == "java.security.egd" and "dev/urandom" in prop_val:
                result["jvm_analysis"]["egd_urandom"] = True
            elif prop_name == "file.encoding":
                result["jvm_analysis"]["file_encoding"] = prop_val

        result["config_analysis"] = {k: v for k, v in configs.items() if k not in ("jvm_args", "flags") and v}

    return result


def build_parser():
    parser = argparse.ArgumentParser(
        prog="spark_toolkit",
        description="Lucko Spark Profile Analyzer Toolkit - AI-first structured JSON output",
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("source", help="spark.lucko.me URL, profile ID, local file path, or inline JSON")
    common.add_argument("--output", "-o", help="Write output to file instead of stdout")
    common.add_argument("--indent", type=int, default=2, help="JSON indent (default: 2, 0 for compact)")

    sub = parser.add_subparsers(dest="command", help="Analysis command")

    # fetch
    p_fetch = sub.add_parser("fetch", parents=[common], help="Fetch profile data from spark.lucko.me")
    p_fetch.add_argument("--full", action="store_true", help="Fetch full data including thread samples")

    # info
    sub.add_parser("info", parents=[common], help="Platform/metadata summary")

    # threads
    p_threads = sub.add_parser("threads", parents=[common], help="List and analyze threads")
    p_threads.add_argument("--thread", "-t", nargs="+", help="Filter threads by name (supports: server, netty, region, or substring)")
    p_threads.add_argument("--top", type=int, default=0, help="Show top N children per thread")
    p_threads.add_argument("--top-threads", type=int, help="Limit to top N threads by time")

    # tree
    p_tree = sub.add_parser("tree", parents=[common], help="Dump profiler tree with filtering")
    p_tree.add_argument("--thread", "-t", nargs="+", help="Filter threads (server, netty, region, or substring)")
    p_tree.add_argument("--plugin", "-p", help="Filter to calls from a specific plugin package")
    p_tree.add_argument("--class-filter", "-c", help="Regex filter on class.method signatures")
    p_tree.add_argument("--min-pct", type=float, default=0.0, help="Minimum percentage to include (default: 0)")
    p_tree.add_argument("--max-depth", type=int, default=100, help="Maximum tree depth (default: 100)")
    p_tree.add_argument("--limit", type=int, help="Limit number of nodes returned")
    p_tree.add_argument("--sort-by-pct", action="store_true", help="Sort nodes by percentage descending")

    # hotspots
    p_hot = sub.add_parser("hotspots", parents=[common], help="Find top CPU/self-time hotspots")
    p_hot.add_argument("--thread", "-t", nargs="+", help="Filter threads")
    p_hot.add_argument("--class-filter", "-c", help="Regex filter on class.method signatures")
    p_hot.add_argument("--min-pct", type=float, default=1.0, help="Minimum self-time %% to report (default: 1)")
    p_hot.add_argument("--exclude-sleep", action="store_true", help="Exclude sleep/park/wait methods")
    p_hot.add_argument("--limit", type=int, default=50, help="Max hotspots to return (default: 50)")

    # plugins
    p_plug = sub.add_parser("plugins", parents=[common], help="Attribute time to plugins/mods")
    p_plug.add_argument("--thread", "-t", nargs="+", help="Filter threads")
    p_plug.add_argument("--plugin", "-p", help="Filter to specific plugin name")

    # tps
    sub.add_parser("tps", parents=[common], help="Extract TPS/MSPT data")

    # gc
    sub.add_parser("gc", parents=[common], help="Extract GC statistics")

    # health
    sub.add_parser("health", parents=[common], help="Parse health report data")

    # heap
    p_heap = sub.add_parser("heap", parents=[common], help="Parse heap summary data")
    p_heap.add_argument("--type-filter", help="Filter heap entries by type name substring")
    p_heap.add_argument("--plugin", "-p", help="Filter to types from a specific plugin package")
    p_heap.add_argument("--limit", type=int, default=30, help="Max entries to return (default: 30)")

    # entities
    p_ent = sub.add_parser("entities", parents=[common], help="Entity/world statistics")
    p_ent.add_argument("--entity-type", help="Filter by entity type name")
    p_ent.add_argument("--min-entities", type=int, help="Minimum entity count per chunk to include")

    # search
    p_search = sub.add_parser("search", parents=[common], help="Search stack trace nodes by pattern")
    p_search.add_argument("pattern", help="Search pattern (substring or regex)")
    p_search.add_argument("--regex", action="store_true", help="Treat pattern as regex")
    p_search.add_argument("--thread", "-t", nargs="+", help="Filter threads")
    p_search.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")

    # callpath
    p_path = sub.add_parser("callpath", parents=[common], help="Trace call path to a specific method")
    p_path.add_argument("method", help="Method/class pattern to trace")
    p_path.add_argument("--regex", action="store_true", help="Treat pattern as regex")
    p_path.add_argument("--thread", "-t", nargs="+", help="Filter threads")
    p_path.add_argument("--limit", type=int, default=10, help="Max paths (default: 10)")

    # compare
    p_cmp = sub.add_parser("compare", parents=[common], help="Compare two time windows")
    p_cmp.add_argument("--window-a", help="First window ID")
    p_cmp.add_argument("--window-b", help="Second window ID")

    # report
    sub.add_parser("report", parents=[common], help="Generate full analysis report with findings")

    # analyze-gc
    sub.add_parser("analyze-gc", parents=[common], help="Deep GC analysis with ZGC/G1GC-specific insights and tuning recommendations")

    # analyze-tps
    sub.add_parser("analyze-tps", parents=[common], help="TPS/MSPT analysis with lag spike detection and window correlation")

    # analyze-cpu
    sub.add_parser("analyze-cpu", parents=[common], help="CPU usage analysis with process/system breakdown and thread attribution")

    # recommend
    sub.add_parser("recommend", parents=[common], help="Comprehensive performance recommendations with priority actions")

    # check-config
    p_check = sub.add_parser("check-config", parents=[common], help="Analyze JVM flags and server configuration files for performance issues and gamemode-specific safety")
    p_check.add_argument("--platform", choices=["paper", "folia", "spigot", "bukkit", "velocity", "bungee"], help="Server platform for config-specific checks")
    p_check.add_argument("--gamemode", choices=["smp", "lobby", "bedwars", "skyblock", "factions", "creative", "modded", "unknown"], default=None, help="Server gamemode for gamemode-aware config review. Default: auto-detect from plugins, fallback to 'unknown' (conservative)")
    p_check.add_argument("--config-dir", help="Path to server directory containing server.properties, spigot.yml, bukkit.yml, paper-global.yml, paper-world.yml")
    p_check.add_argument("--server-properties", help="Path to server.properties file")
    p_check.add_argument("--spigot-yml", help="Path to spigot.yml file")
    p_check.add_argument("--bukkit-yml", help="Path to bukkit.yml file")
    p_check.add_argument("--paper-global-yml", help="Path to paper-global.yml file")
    p_check.add_argument("--paper-world-yml", help="Path to paper-world.yml or paper-world-defaults.yml file")
    p_check.add_argument("--canvas-config", help="Path to canvas-server.json5 file")
    p_check.add_argument("--velocity-config", help="Path to velocity.toml file")
    p_check.add_argument("--pufferfish-config", help="Path to pufferfish.yml file")
    p_check.add_argument("--purpur-config", help="Path to purpur.yml file")

    # pipeline
    p_pipeline = sub.add_parser("pipeline", parents=[common], help="Analyze netty pipeline handler chain and detect duplicate shaded handlers")
    p_pipeline.add_argument("--thread", "-t", nargs="+", default=["netty"], help="Netty thread name filter (default: netty)")
    p_pipeline.add_argument("--detect-duplicates", action="store_true", help="Detect and warn about duplicate shaded handlers in the pipeline")

    # plugin-heap
    p_pluginheap = sub.add_parser("plugin-heap", parents=[common], help="Heap usage attributed to a specific plugin")
    p_pluginheap.add_argument("--plugin", "-p", required=True, help="Plugin name or package to attribute heap to")
    p_pluginheap.add_argument("--limit", type=int, default=30, help="Max entries to return (default: 30)")

    # plugin-profile
    p_pluginprofile = sub.add_parser("plugin-profile", parents=[common], help="Complete plugin performance profile (CPU + heap + findings)")
    p_pluginprofile.add_argument("--plugin", "-p", required=True, help="Plugin name or package to profile")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "fetch": cmd_fetch,
        "info": cmd_info,
        "threads": cmd_threads,
        "tree": cmd_tree,
        "hotspots": cmd_hotspots,
        "plugins": cmd_plugins,
        "tps": cmd_tps,
        "gc": cmd_gc,
        "health": cmd_health,
        "heap": cmd_heap,
        "entities": cmd_entities,
        "search": cmd_search,
        "callpath": cmd_callpath,
        "compare": cmd_compare,
        "report": cmd_report,
        "analyze-gc": cmd_analyze_gc,
        "analyze-tps": cmd_analyze_tps,
        "analyze-cpu": cmd_analyze_cpu,
        "recommend": cmd_recommend,
        "check-config": cmd_check_config,
        "pipeline": cmd_pipeline,
        "plugin-heap": cmd_plugin_heap,
        "plugin-profile": cmd_plugin_profile,
    }

    handler = commands.get(args.command)
    if not handler:
        print(f"Unknown command: {args.command}")
        sys.exit(1)

    try:
        result = handler(args)
    except urllib.error.HTTPError as e:
        result = {"error": f"HTTP {e.code}: {e.reason}", "url": str(e.url) if hasattr(e, 'url') else ""}
    except FileNotFoundError as e:
        result = {"error": f"File not found: {e}"}
    except json.JSONDecodeError as e:
        result = {"error": f"Invalid JSON: {e}"}
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