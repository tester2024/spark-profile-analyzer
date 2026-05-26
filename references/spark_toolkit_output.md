# Spark Toolkit Output Formats & Status Assessments

Health assessment thresholds, status levels, and output format details for `spark_toolkit.py` commands.

## Thread Health Assessment

The `threads` command automatically assesses thread health based on sleep percentage:

| Sleep % | Health | Meaning |
|---|---|---|
| >50% | HEALTHY | Server has spare capacity |
| 20-50% | MODERATE | Working hard but coping |
| <20% | OVERLOADED | No spare capacity, likely lagging |

## TPS/MSPT Status Levels

TPS and MSPT values are automatically assessed in the `tps` command:

| Metric | GOOD | WARNING | CRITICAL |
|---|---|---|---|
| TPS | >= 19.5 | 15 - 19.5 | < 15 |
| MSPT median | < 30ms | 30 - 45ms | > 45ms |
| MSPT P95 | < 45ms | 45 - 60ms | > 60ms |
| MSPT max | < 50ms | 50 - 150ms | > 150ms |
| GC frequency | < 1/min | 1 - 5/min | > 5/min |
| GC avg pause | < 50ms | 50 - 200ms | > 200ms |

## Plugin-Heap Assessment Levels

The `plugin-heap` command reports assessment levels:

| Assessment | Threshold |
|---|---|
| CRITICAL | Plugin uses > 10% of total heap |
| WARNING | Plugin uses > 5% of total heap |
| LOW | Plugin uses <= 5% of total heap |

## Report Output Format

The `report` command generates a full analysis. Output includes:
- Platform info
- TPS/MSPT data
- GC statistics
- Thread health assessment
- Top hotspots per thread
- Plugin/source time attribution
- Heap summary with plugin attribution
- Heap usage by plugin (with warnings for heavy consumers)
- Auto-generated findings with severity levels (CRITICAL/WARNING/LOW)

## Plugin-Profile Output Format

The `plugin-profile` command provides a complete performance overview. Output includes:
- Plugin metadata (version, author)
- CPU time breakdown by thread
- Top hot methods with self-time percentages
- Percentage of Server thread consumed
- Heap usage attributed to the plugin
- Allocation hotspots (from `--alloc` profiles)
- GC pressure indicators
- Auto-generated findings with severity levels