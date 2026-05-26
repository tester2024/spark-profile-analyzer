# BungeeCord/Velocity Proxy Configuration Reference

---

## velocity.toml

### [servers] Section

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| Section header | Defines backend servers | — | List all backend servers | Required for proxy routing. |

Example:
```toml
[servers]
lobby = "127.0.0.1:25566"
survival = "127.0.0.1:25567"
creative = "127.0.0.1:25568"
```

### [forced-hosts] Section

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| Section header | Maps hostnames to specific servers | — | Configure per-domain routing | Players connecting with matching hostname skip server list and go to forced server. |

Example:
```toml
[forced-hosts]
"play.example.com" = "survival"
"creative.example.com" = "creative"
```

### [advanced] Section

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `compression-threshold` | Min packet size to compress | 256 | 256-512 | **Medium** - 256 balances CPU/bandwidth. 512 reduces CPU at cost of bandwidth. -1 disables. |
| `compression-level` | Zlib compression level | -1 | -1 to 4 | **Medium** - -1 = default (6). 1-4 = faster, larger packets. 7-9 = slower, smaller. Use 1-4 for CPU savings. |
| `hints-timeout` | SRV record lookup timeout (ms) | 5000 | 3000-5000 | **Low** - only affects initial connection. |
| `connection-timeout` | Backend connection timeout (ms) | 5000 | 3000-5000 | **Low** - timeout for connecting to backend servers. |
| `read-timeout` | Client read timeout (ms) | 30000 | 30000 | **Low** - how long to wait for client data before disconnect. |
| `proxy-protocol` | Send HAProxy PROXY protocol | false | false (true if behind HAProxy) | **Low** - only needed if using HAProxy/load balancer that sends PROXY protocol headers. |
| `quick-play` | Allow quick play (Mojang API) | false | false on prod | **Low** - experimental, can cause login issues. |

### [query] Section

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `enabled` | Enable GS4 query protocol | false | false | **Low** - expose server info. Disable for security. |
| `port` | Query port | 25577 | Keep default | **None** - only used if query enabled. |
| `show-plugins` | Show plugins in query | false | false | **None** - security: don't expose plugin list. |

### Core Settings

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `bind` | Proxy bind address | 0.0.0.0:25565 | Specific IP if multi-homed | **None** - network config. |
| `motd` | Message of the day | A Velocity Server | Customize | **None** - cosmetic. |
| `show-max-players` | Displayed max players | 500 | Actual limit | **None** - cosmetic. |
| `player-info-forwarding` | How to forward player data | NONE | LEGACY (BungeeCord) or MODERN (Velocity) | **Critical** - MODERN uses HMAC-SHA256. LEGACY is BungeeCord format. MODERN is recommended. |
| `forwarding-secret-file` | Secret file for modern forwarding | forwarding.secret | Generate unique secret | **Critical** - prevents IP spoofing. Never use empty secret in production. |
| `kick-existing-players` | Kick online player if same name joins | false | false | **Medium** - true allows session stealing but prevents "already connected" errors. |
| `connection-throttling` | MS between connections from same IP | 250 | 500-1000 | **Low-Medium** - prevents connection floods. Higher = more protection but may affect legit reconnects. |

### [loggers] Section

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `level` | Log level | info | info | **None** - debug is very verbose. |

---

## BungeeCord config.yml

### Core Settings

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `connection_throttle` | MS between connections from same IP | 4000 | 2000-5000 | **Low-Medium** - prevents connection floods. Too low = flood risk. Too high = legit reconnects blocked. |
| `connection_throttle_limit` | Max connections before throttle | 3 | 3-5 | **Low** - number of allowed rapid connections before throttle kicks in. |
| `timeout` | Network timeout (ms) | 30000 | 15000-30000 | **Medium** - how long to wait before disconnecting unresponsive clients. 15000 for aggressive cleanup. |
| `network_compression_threshold` | Packet compression threshold | 256 | 256-512 | **Medium** - same as Velocity. 256 balanced, 512 less CPU, -1 disabled. |
| `server_connect_timeout` | Backend connect timeout (ms) | 5000 | 3000-5000 | **Low** - timeout for backend server connections. |
| `enforce_secure_profile` | Enforce secure chat profiles | true | true | **None** - 1.19.1+ chat signing. |

### Server Definitions

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `servers` | Backend server list | — | Define all backends | Required. Each server needs address + name. |
| `motd` | Per-server MOTD | — | Optional | **None** |
| `restricted` | Restrict server to specific groups | false | As needed | **None** |

### Listeners

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `host` | Bind address | 0.0.0.0:25577 | Specific IP if multi-homed | **None** |
| `max_players` | Displayed max players | 100 | Actual limit | **None** - cosmetic |
| `force_default_server` | Force players to default server | false | false | **None** - true ignores last server. |
| `priorities` | Server fallback order | [lobby] | [lobby, fallback1] | **None** - determines fallback server if primary is down. |
| `ping_passthrough` | Forward backend server ping | false | false | **Low** - true can add latency to status pings. |

### Player Limits & Throttling

| Config | What it does | Default | Recommended | Impact |
|--------|-------------|---------|-------------|--------|
| `max_players` | True player limit | 100 | Set to actual capacity | **Medium** - rejects connections above limit. |
| `player_limit` | Per-server player limit | -1 (none) | Set per server capacity | **Medium** - distributes load across backends. |
| `connection_throttle` | Global connection throttle | 4000 | 2000-5000 | **Medium** |
| `connection_throttle_limit` | Connections before throttle | 3 | 3-5 | **Low** |

### Tab List & Permissions

| Config | What it does | Default | Impact |
|-------- |-------------|---------|--------|
| `tab_list` | Tab list format | GLOBAL_PING | **None** - cosmetic |
| `permissions` | Permission groups | default: [all] | **None** - access control |

---

## Proxy JVM Flags

Proxies are I/O-bound, not CPU-bound like game servers. They benefit from different tuning.

### Recommended JVM Flags (Velocity/BungeeCord)

```
-Xms1G -Xmx1G
-XX:+UseG1GC
-XX:+ParallelRefProcEnabled
-XX:MaxGCPauseMillis=100
-XX:+AlwaysPreTouch
-XX:+DisableExplicitGC
```

### Proxy Memory Sizing

| Scale | Players | Recommended Xmx |
|-------|---------|----------------|
| Small | < 200 | 512MB - 1GB |
| Medium | 200-500 | 1GB - 2GB |
| Large | 500-1000 | 2GB - 4GB |
| Very Large | 1000+ | 4GB - 8GB |

**Note**: Proxies use far less memory than game servers. The bottleneck is network I/O and connection handling, not heap. A 1GB proxy can handle hundreds of players.

### Proxy-Specific Tuning

| Tuning | What it does | When to use |
|--------|-------------|-------------|
| Increase ulimit | Raise file descriptor limit | Any proxy. `ulimit -n 10000` or higher. |
| Network buffer sizing | TCP buffer sizes | Large proxies. `net.core.rmem_max=16777216` |
| epoll/kqueue | Use native transport | Automatic in Netty (Velocity). Ensure lib is available. |
| Disable DNS lookup | Skip reverse DNS on connect | BungeeCord: set `disable_player_fighting` or use plugin. Velocity: default. |

---

## Velocity vs BungeeCord Comparison

| Feature | Velocity | BungeeCord | Recommendation |
|---------|----------|------------|----------------|
| Performance | Higher throughput, lower latency | Good but older | **Velocity** for new setups |
| Security | Modern forwarding with HMAC | Legacy forwarding only | **Velocity** |
| Plugin compatibility | Needs Velocity plugins | Larger plugin ecosystem | BungeeCord if plugins needed |
| Configuration | Clean TOML format | YAML | Velocity |
| Active development | Active, modern | Maintained, legacy | Velocity |
| Multi-protocol | Excellent 1.8-1.21+ | Good | Velocity |
| TCP optimization | Better Netty defaults | Adequate | Velocity |

---

## Load Balancer Configuration

When using a load balancer (HAProxy, nginx stream) in front of a proxy:

### HAProxy Example

```
frontend minecraft
    bind *:25565
    mode tcp
    default_backend minecraft_servers

backend minecraft_servers
    mode tcp
    balance leastconn
    server proxy1 127.0.0.1:25566 check
    server proxy2 127.0.0.1:25567 check
```

### When proxy-protocol is needed

- Only enable `proxy-protocol` on Velocity/BungeeCord if your load balancer sends PROXY protocol v1/v2 headers
- This preserves the real client IP through the load balancer
- **Without** proxy-protocol: all connections appear from the load balancer IP (breaks IP-based features)
- **With** proxy-protocol: real client IP is forwarded (requires load balancer support)

### TCP Keepalive

| Setting | Recommended | Why |
|---------|-------------|-----|
| TCP keepalive time | 60s | Detect dead connections quickly |
| TCP keepalive interval | 10s | Retry interval |
| TCP keepalive probes | 3 | Consecutive failures before disconnect |

---

## Common Proxy Misconfigurations

| Misconfiguration | Problem | Fix |
|-----------------|---------|-----|
| No forwarding secret | IP spoofing vulnerability | Generate unique secret for MODERN forwarding |
| online-mode=true on backends | Authentication conflict with proxy | Set online-mode=false on backend, proxy handles auth |
| Too much RAM for proxy | Wasted resources, bigger GC pauses | 1-2GB is sufficient for most proxies |
| No connection throttle | Flood vulnerability | Set 2000-5000ms |
| compression-threshold=-1 on WAN | Excessive bandwidth usage | Keep at 256-512 for internet-facing proxies |
| No fallback/lobby | Players kicked when backend down | Configure priorities with fallback server |
| BungeeCord without firewall | Direct backend access | Firewall backend ports, only allow proxy IP |