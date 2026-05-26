#!/usr/bin/env python3
"""
Lucko Spark Profile Analyzer Toolkit

Comprehensive CLI tool for fetching, parsing, filtering, and analyzing
Lucko Spark profiler data from spark.lucko.me URLs and local files.

Designed as an AI-first utility: all output is structured JSON for easy
parsing by agents. Every command supports filtering to target specific
threads, plugins, classes, methods, and time windows.

Usage:
    python spark_toolkit.py <command> [options]

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

Run 'python spark_toolkit.py <command> --help' for command-specific options.
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
from collections import defaultdict
from pathlib import Path

SPARK_VIEWER_BASE = "https://spark.lucko.me"
SPARK_RAW_BASE = "https://spark-usercontent.lucko.me"


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
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def load_data(source):
    if source.startswith("http://") or source.startswith("https://"):
        pid = extract_id(source)
        try:
            return fetch_json(pid, full=True), "json_url"
        except Exception:
            return None, None
    if re.match(r'^[a-zA-Z0-9]{4,20}$', source):
        try:
            return fetch_json(source, full=True), "json_url"
        except Exception:
            return None, None
    if os.path.isfile(source):
        with open_file(source) as f:
            content = f.read()
        try:
            data = json.loads(content)
            return data, "file_json"
        except json.JSONDecodeError:
            return {"_raw_file": source, "_format": "protobuf_or_binary"}, "file_raw"
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
    result = {
        "type": type_map.get(pm.get("type", 0), "UNKNOWN"),
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

    configs = meta.get("serverConfigurations", meta.get("server_configurations", {}))
    if configs:
        result["jvm_flags"] = configs.get("jvm_args", configs.get("flags", ""))

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
        result["sampler"] = {
            "interval_ms": meta.get("interval", 4),
            "mode": mode,
            "engine": engine,
            "aggregator_type": sampler_meta.get("type"),
            "thread_grouper": sampler_meta.get("threadGrouper", sampler_meta.get("thread_grouper")),
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

    for t in threads:
        name = t.get("name", "unknown")
        if not thread_matches(name, thread_filters):
            continue

        times = t.get("times", [])
        total_time = sum(times) if times else 0
        children = t.get("children", [])

        child_time = sum(sum(c.get("times", [])) for c in children if c.get("times"))
        sleep_time = 0
        sleep_names = {"waitForNextTick", "Thread.sleep", "LockSupport.park", "Object.wait", "Unsafe.park", "park"}
        tick_time = 0
        tick_names = {"tick", "doTick", "runTick"}

        for c in children:
            mn = c.get("methodName", c.get("method_name", ""))
            ct_list = c.get("times", [])
            ct_sum = sum(ct_list) if ct_list else 0
            if any(s in mn for s in sleep_names):
                sleep_time += ct_sum
            if any(tk in mn for tk in tick_names):
                tick_time += ct_sum

        entry = {
            "name": name,
            "total_time": total_time,
            "sleep_time": sleep_time,
            "sleep_pct": pct(sleep_time, total_time),
            "tick_time": tick_time,
            "tick_pct": pct(tick_time, total_time),
            "other_time": total_time - sleep_time - tick_time,
            "child_count": len(children),
        }

        sleep_pct_val = pct(sleep_time, total_time)
        if sleep_pct_val >= 50:
            entry["health"] = "HEALTHY"
        elif sleep_pct_val >= 20:
            entry["health"] = "MODERATE"
        else:
            entry["health"] = "OVERLOADED"

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
                    sleep_names = {"waitfornexttick", "thread.sleep", "locksupport.park", "object.wait", "unsafe.park"}
                    if any(s in h["method"].lower() for s in sleep_names):
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
    if "tps" in pstats:
        t = pstats["tps"]
        result["tps"] = {
            "1m": {"value": t.get("last1m"), "status": assess_tps(t.get("last1m", 0))},
            "5m": {"value": t.get("last5m"), "status": assess_tps(t.get("last5m", 0))},
            "15m": {"value": t.get("last15m"), "status": assess_tps(t.get("last15m", 0))},
            "target": t.get("gameTargetTps", t.get("game_target_tps", 20)),
        }

    if "mspt" in pstats:
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

    if pstats and "tps" in pstats:
        for period, key in [("1m", "last1m"), ("5m", "last5m"), ("15m", "last15m")]:
            val = pstats["tps"].get(key, 20)
            if val < 15:
                findings.append({"severity": "CRITICAL", "category": "tps", "detail": f"TPS {period}m is {val}, server is severely lagging"})
            elif val < 19.5:
                findings.append({"severity": "WARNING", "category": "tps", "detail": f"TPS {period}m is {val}, below ideal 20"})

    if pstats and "mspt" in pstats:
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
            sleep_names = {"waitForNextTick", "Thread.sleep", "LockSupport.park", "Object.wait", "Unsafe.park", "park"}
            for c in children:
                mn = c.get("methodName", c.get("method_name", ""))
                if any(s in mn for s in sleep_names):
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