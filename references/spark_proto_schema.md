# Spark Proto Schema Reference

Full protobuf schema reference for Lucko Spark profile data.

## Content Types

| Content-Type | Message | Description |
|---|---|---|
| `application/x-spark-sampler` | `SamplerData` | CPU/allocation profiler data |
| `application/x-spark-heap` | `HeapData` | Heap summary data |
| `application/x-spark-health` | `HealthData` | Health report data |

## SamplerData

```protobuf
message SamplerData {
  SamplerMetadata metadata = 1;
  repeated ThreadNode threads = 2;
  map<string, string> class_sources = 3;   // class -> plugin/mod source
  map<string, string> method_sources = 4;  // method -> plugin/mod source
  map<string, string> line_sources = 5;    // line -> plugin/mod source
  repeated int32 time_windows = 6;
  map<int32, WindowStatistics> time_window_statistics = 7;
  SocketChannelInfo channel_info = 8;
}
```

### SamplerMetadata

```protobuf
message SamplerMetadata {
  CommandSenderMetadata creator = 1;
  int64 start_time = 2;
  int32 interval = 3;                    // sampling interval in ms (default 4)
  ThreadDumper thread_dumper = 4;
  DataAggregator data_aggregator = 5;
  string comment = 6;
  PlatformMetadata platform_metadata = 7;
  PlatformStatistics platform_statistics = 8;
  SystemStatistics system_statistics = 9;
  map<string, string> server_configurations = 10;
  int64 end_time = 11;
  int32 number_of_ticks = 12;
  map<string, PluginOrModMetadata> sources = 13;
  map<string, string> extra_platform_metadata = 14;
  SamplerMode sampler_mode = 15;         // EXECUTION=0 or ALLOCATION=1
  SamplerEngine sampler_engine = 16;     // JAVA=0 or ASYNC=1
  string sampler_engine_version = 17;
}
```

### ThreadDumper

```protobuf
message ThreadDumper {
  Type type = 1;            // ALL=0, SPECIFIC=1, REGEX=2
  repeated int64 ids = 2;   // thread IDs (if SPECIFIC)
  repeated string patterns = 3; // regex patterns (if REGEX)
}
```

### DataAggregator

```protobuf
message DataAggregator {
  Type type = 1;                         // SIMPLE=0, TICKED=1
  ThreadGrouper thread_grouper = 2;     // BY_NAME=0, BY_POOL=1, AS_ONE=2
  int64 tick_length_threshold = 3;      // --only-ticks-over value in ms
  int32 number_of_included_ticks = 4;  // ticks that met threshold
}
```

### ThreadNode

```protobuf
message ThreadNode {
  string name = 1;                      // thread name (e.g. "Server thread")
  repeated StackTraceNode children = 3; // root call frames
  repeated double times = 4;            // time samples per window
  repeated int32 children_refs = 5;     // child node indices
}
```

### StackTraceNode

```protobuf
message StackTraceNode {
  string class_name = 3;
  string method_name = 4;
  int32 parent_line_number = 5;  // optional
  int32 line_number = 6;         // optional
  string method_desc = 7;        // optional (JVM method descriptor)
  repeated double times = 8;            // time samples per window
  repeated int32 children_refs = 9;     // child node indices
}
```

## HeapData

```protobuf
message HeapData {
  HeapMetadata metadata = 1;
  repeated HeapEntry entries = 2;
}

message HeapEntry {
  int32 order = 1;        // sort order
  int32 instances = 2;    // number of instances
  int64 size = 3;         // total size in bytes
  string type = 4;        // class name
}
```

## HealthData

```protobuf
message HealthData {
  HealthMetadata metadata = 1;
  map<int32, WindowStatistics> time_window_statistics = 2;
}
```

## Supporting Messages

### PlatformMetadata

```protobuf
message PlatformMetadata {
  Type type = 1;            // SERVER=0, CLIENT=1, PROXY=2, APPLICATION=3
  string name = 2;          // e.g. "Bukkit", "Fabric"
  string version = 3;       // e.g. "git-Paper-386 (MC: 1.19.3)"
  string minecraft_version = 4;
  int32 spark_version = 7;
  string brand = 8;
}
```

### PlatformStatistics

```protobuf
message PlatformStatistics {
  Memory memory = 1;
  map<string, Gc> gc = 2;
  int64 uptime = 3;
  Tps tps = 4;          // optional
  Mspt mspt = 5;        // optional
  Ping ping = 6;        // optional
  int64 player_count = 7;
  WorldStatistics world = 8;
  OnlineMode online_mode = 9;

  message Tps {
    double last1m = 1;
    double last5m = 2;
    double last15m = 3;
    int32 game_target_tps = 4;  // usually 20
  }

  message Mspt {
    RollingAverageValues last1m = 1;
    RollingAverageValues last5m = 2;
    int32 game_max_ideal_mspt = 3;  // usually 50
  }

  message Memory {
    MemoryUsage heap = 1;
    MemoryUsage non_heap = 2;
    repeated MemoryPool pools = 3;
  }

  message Gc {
    int64 total = 1;
    double avg_time = 2;
    double avg_frequency = 3;
  }
}
```

### SystemStatistics

```protobuf
message SystemStatistics {
  Cpu cpu = 1;
  Memory memory = 2;
  map<string, Gc> gc = 3;
  Disk disk = 4;
  Os os = 5;
  Java java = 6;
  int64 uptime = 7;
  map<string, NetInterface> net = 8;
  Jvm jvm = 9;

  message Cpu {
    int32 threads = 1;
    Usage process_usage = 2;   // last1m, last15m
    Usage system_usage = 3;
    string model_name = 4;
  }

  message Memory {
    MemoryPool physical = 1;  // used, total
    MemoryPool swap = 2;
  }

  message Gc {
    int64 total = 1;
    double avg_time = 2;
    double avg_frequency = 3;
  }
}
```

### WindowStatistics

```protobuf
message WindowStatistics {
  int32 ticks = 1;
  double cpu_process = 2;
  double cpu_system = 3;
  double tps = 4;
  double mspt_median = 5;
  double mspt_max = 6;
  int32 players = 7;
  int32 entities = 8;
  int32 tile_entities = 9;
  int32 chunks = 10;
  int64 start_time = 11;
  int64 end_time = 12;
  int32 duration = 13;
}
```

### RollingAverageValues

```protobuf
message RollingAverageValues {
  double mean = 1;
  double max = 2;
  double min = 3;
  double median = 4;
  double percentile95 = 5;
}
```

### WorldStatistics

```protobuf
message WorldStatistics {
  int32 total_entities = 1;
  map<string, int32> entity_counts = 2;
  repeated World worlds = 3;
  repeated GameRule game_rules = 4;
  repeated DataPack data_packs = 5;

  message World {
    string name = 1;
    int32 total_entities = 2;
    repeated Region regions = 3;
  }

  message Region {
    int32 total_entities = 1;
    repeated Chunk chunks = 2;
  }

  message Chunk {
    int32 x = 1;
    int32 z = 2;
    int32 total_entities = 3;
    map<string, int32> entity_counts = 4;
  }
}
```

## Fetching & Parsing Pipeline

1. Fetch raw protobuf from `https://spark-usercontent.lucko.me/<id>`
2. Check `Content-Type` header to determine message type
3. Decode using the appropriate protobuf schema
4. Extract `SamplerMetadata` for platform/context info
5. Walk `ThreadNode` tree for CPU热点 analysis
6. Correlate with `WindowStatistics` for TPS/MSPT trends
7. Cross-reference `class_sources` / `method_sources` to attribute calls to plugins/mods