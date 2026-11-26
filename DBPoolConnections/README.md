# Database Connection Pool (DBPool) Prototype

An educational prototype in Go demonstrating how a **Database Connection Pool** works from scratch, compared against creating direct (one-off) database connections.

---

## 🧠 Why Connection Pooling?

### 1. Direct Connection (No Pool)
For **every single query**, the client must perform:
```text
Client                                             PostgreSQL Server
  │                                                        │
  ├──── TCP SYN ──────────────────────────────────────────>│ (1. TCP 3-way handshake)
  │<─── TCP SYN-ACK ───────────────────────────────────────┤
  ├──── TCP ACK ──────────────────────────────────────────>│
  │                                                        │
  ├──── Startup Message (User, DB) ───────────────────────>│ (2. Fork process & Auth)
  │<─── Authentication Request (MD5 / SCRAM) ──────────────┤    *Postgres forks a backend worker!*
  ├──── Password / SASL Response ─────────────────────────>│
  │<─── AuthenticationOk + ReadyForQuery ──────────────────┤
  │                                                        │
  ├──── Query: SELECT 1 FROM pg_sleep(0.01) ──────────────>│ (3. Query execution)
  │<─── Result: 1 ─────────────────────────────────────────┤
  │                                                        │
  ├──── Terminate (TCP FIN) ──────────────────────────────>│ (4. Connection Teardown)
  │<─── TCP ACK / FIN ─────────────────────────────────────┤
```
- **Cost**: High latency (~10–30ms+ overhead per query just for socket and auth handshakes), high CPU/RAM usage on PostgreSQL (Postgres forks a separate OS process for each client connection).

---

### 2. Pooled Connection (DBPool)
Connections are opened **once** and reused across many queries:
```text
[Pre-warmed Pool] ──> [Queue of Idle TCP Sockets]
                              │
  Query 1: Acquire ──────────>│ (Instant! Reuses existing socket)
           Execute Query
           Release ──────────>│ (Returns socket to idle queue)
                              │
  Query 2: Acquire ──────────>│ (Instant!)
           Execute Query
           Release ──────────>│
```
- **Cost**: Socket and authentication happen once upfront. Query latency is purely the network transmission and SQL execution time.

---

## 🛠 Project Structure

- `pool.go`: Minimal thread-safe connection pool (`SimplePool`) using a Go buffered channel as a bounded blocking queue with configurable `minConn` and `maxConn`.
- `main.go`: Benchmarking suite comparing direct connections vs. pooled connections running `SELECT 1 FROM pg_sleep(0.01)`.
- `docker-compose.yml`: Local PostgreSQL container setup.

---

## 🚀 Quickstart & Docker Setup

### Step 1: Start PostgreSQL via Docker

Run using Docker Compose:
```bash
docker compose up -d
```

*(Alternatively, run with standalone docker):*
```bash
docker run --name dbpool_postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=testdb \
  -p 5432:5432 \
  -d postgres:16-alpine
```

Verify the container is healthy:
```bash
docker ps
```

---

### Step 2: Run the Prototype

Run the Go prototype:
```bash
go run -ldflags="-linkmode=external" .
```

> [!NOTE]
> If you are on macOS 15 (Sequoia) with Go <= 1.22.6, Apple's `dyld` requires the `-ldflags="-linkmode=external"` flag because of a known Go bug where the internal linker omitted `LC_UUID`. Upgrading Go via `brew upgrade go` (Go 1.22.7+ or 1.23+) also permanently fixes this.

To stop the PostgreSQL container when done:
```bash
docker compose down
```

---

## 📊 Experiments & Expected Results

### 1. Burst / Spike Test (150 Simultaneous Requests)
When 150 concurrent queries hit PostgreSQL (default limit `max_connections = 100`) simultaneously:

```text
==================================================================
 💥 BURST EXPERIMENT: 150 SIMULTANEOUS REQUESTS
 Postgres limit = 100 | In-flight sleep = 50ms
==================================================================

[1] Firing 150 simultaneous queries with DIRECT CONNECTIONS...

--- Direct Connection Burst Result ---
✅ Successful Queries:  97 / 150
❌ Failed Queries:      53 / 150
💥 Postgres Error:      "FATAL: sorry, too many clients already (SQLSTATE 53300)"

------------------------------------------------------------------
[2] Firing 150 simultaneous queries through DBPool (MaxConn=10)...

--- Simple DBPool Burst Result ---
✅ Successful Queries:  150 / 150
❌ Failed Queries:      0 / 150
🛡 Max Conns Opened:    10 (Safely below Postgres limit of 100!)
Final Pool State:       Total=10, Idle=10, Active=0

==================================================================
 🎯 KEY TAKEAWAY
==================================================
• Without DBPool: Direct connections overwhelmed Postgres (53 queries crashed with 'too many clients')
• With DBPool:    The pool buffered the spike to 10 safe connections (150 queries succeeded, 0 failed!)
==================================================================
```
