
# Go + MySQL Setup

## 1. Prerequisites

Install the following:
- Docker Desktop
- Go 1.21+

Verify installations:

```bash
docker --version
docker compose version
go version
```

## 2. Start MySQL Database

From the project root directory, run:

```bash
docker compose up -d
```

Verify the container:

```bash
docker ps
```

Check MySQL logs:

```bash
docker logs -f mysql-dev
```

## 3. Database Configuration

| Parameter | Value |
|---|---|
| Host | localhost |
| Port | 3306 |
| Database | app_db |
| Username | app_user |
| Password | app123 |

**Database Connection String:**

```text
app_user:app123@tcp(localhost:3306)/app_db?parseTime=true
```

## 4. Install Go Dependencies

Initialize Go module:

```bash
go mod init mysql-go-demo
```

Install MySQL driver:

```bash
go get github.com/go-sql-driver/mysql
```

Download dependencies:

```bash
go mod tidy
```

## 5. Run Go Application

```bash
go run main.go
```

Expected output:

```text
Successfully connected to MySQL!
MySQL Version: 8.4.x
Users table is ready!
Inserted user ID: 1

Users:
ID: 1 | Name: Rajesh | Email: rajesh@example.com
```

## 6. Access MySQL CLI

Connect to MySQL:

```bash
docker exec -it mysql-dev mysql -uapp_user -p
```

Password: `app123`

Execute SQL queries:

```sql
USE app_db;
SHOW TABLES;
SELECT * FROM users;
```

## 7. Docker Commands

| Operation | Command |
|---|---|
| Start DB | `docker compose start` |
| Stop DB | `docker compose stop` |
| Restart DB | `docker compose restart` |
| Remove container | `docker compose down` |
| Delete DB and data | `docker compose down -v` |

**Important:** `docker compose down -v` permanently deletes the database and its stored data.

## 8. Quick Start

For subsequent runs:

```bash
docker compose up -d
go run main.go
```

**Note:** Credentials are for local development only. Use secure credentials in production.
