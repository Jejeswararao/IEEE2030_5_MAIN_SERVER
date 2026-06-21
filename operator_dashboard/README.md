# IEEE 2030.5 Main Server

This repository contains a Python implementation of an IEEE 2030.5 / SEP-style server for DER telemetry, DER control generation, and operator monitoring. The server exposes IEEE 2030.5 XML endpoints over HTTPS with mutual TLS, stores meter updates in SQLite, evaluates simple IEEE 1547-inspired Volt-VAR / Volt-Watt logic, and provides a separate operator dashboard for live visibility and server control.

The project is organized as two cooperating applications:

- `server/`: the IEEE 2030.5 server that DER clients connect to on port `8443`.
- `operator_dashboard/`: a browser dashboard that operators use on port `8080` to view status, logs, database tables, clients, and start/stop the SEP server.

## Main Capabilities

- HTTPS server with mutual TLS client certificate verification.
- IEEE 2030.5 discovery and DER resource endpoints.
- Metering update ingestion through `/mup`.
- Latest metering readback through `/mup_read`.
- DER program and DER control list endpoints.
- Background control loop that checks voltage conditions every 5 seconds.
- SQLite persistence for metering data and generated controls.
- Runtime logging to `server_runtime.log`.
- Operator dashboard with login, pending registration approval, live charts, logs, table views, client request summaries, and SEP start/stop controls.

## Repository Layout

```text
IEEE2030_5_MAIN_SERVER/
  certs/                         TLS certificate authority, server cert, and client cert material
  operator_dashboard/
    dashboard_server.py           Operator dashboard web server
    README.md                     Dashboard-specific notes
    data/operators.db             Dashboard operator account database
    static/
      dashboard.js                Live polling and chart rendering
      style.css                   Dashboard styling
      theme.js                    Light/dark theme handling
  security/
    lfdi.py                       Top-level LFDI/SFDI helper
    acl.py                        Placeholder
    pki.py                        Placeholder
  server/
    main.py                       SEP server entry point
    config/server_config.py       Host, port, cert, CA, and DB config constants
    core/
      http_server.py              HTTP method handler
      router.py                   URL router
      tls_context.py              Mutual TLS SSL context setup
    control_engine/
      control_logic.py            Measurement evaluation and DER control creation
      ieee1547_controller.py      Volt-VAR / Volt-Watt interpolation logic
    database/
      database.py                 SQLite connection, query, execute, and init helpers
      ieee2030.db                 SEP server SQLite database
    function_sets/
      dcap.py                     DeviceCapability endpoint
      end_device.py               EndDevice endpoint
      der.py                      DER endpoint
      der_program.py              DERProgramList endpoint
      der_control.py              DERControlList endpoint
      mup.py                      Metering update POST handler
      mup_read.py                 Latest metering GET handler
    security/
      lfdi.py                     Server-package LFDI/SFDI helper
      acl.py                      Placeholder
      pki_validator.py            Placeholder
    utils/runtime_logger.py       Console and file logging setup
  server_runtime.log              Runtime log written by the SEP server
  dashboard_started_sep.log       SEP output when launched from the dashboard
```

Generated `__pycache__/` folders are Python bytecode cache folders and are not part of the application design.

## Runtime Architecture

The server starts in `server/main.py`:

1. A runtime logger is configured.
2. A daemon background thread starts `background_control_loop()`.
3. The loop calls `evaluate_and_create_event()` every 5 seconds.
4. An `HTTPServer` is created on `0.0.0.0:8443`.
5. The socket is wrapped with the TLS context from `server/core/tls_context.py`.
6. The server begins handling requests forever.

Request handling flows like this:

```text
DER client
  -> HTTPS + client certificate
  -> server.core.http_server.IEEEHandler
  -> server.core.router.route_request()
  -> server.function_sets.<handler>
  -> optional SQLite read/write
  -> IEEE 2030.5 XML response
```

The operator dashboard is separate. It runs an ordinary HTTP server on port `8080` and reads the SEP database and runtime logs. It can also launch `python -m server.main` as a subprocess.

## Requirements

The code uses mostly Python standard-library modules. The only non-standard Python package currently imported by server code is:

- `numpy`, used by `server/control_engine/ieee1547_controller.py` for interpolation.

Install it into the Python environment used to run the server:

```bash
python -m pip install numpy
```

If `python` points to the wrong executable on Windows, use the full path to your intended Python installation.

## Running the IEEE 2030.5 Server

From the project root:

```bash
python -m server.main
```

The server listens on:

```text
https://0.0.0.0:8443
```

Because mutual TLS is enabled, clients must present a certificate signed by the configured CA.

The main startup log messages are:

```text
IEEE 2030.5 SERVER RUNNING
PORT: 8443
Mutual TLS ENABLED
Waiting for DER devices...
```

## Running the Operator Dashboard

From the project root:

```bash
python operator_dashboard/dashboard_server.py
```

Open:

```text
http://localhost:8080/login
```

The dashboard port can be changed with:

```bash
OPERATOR_DASHBOARD_PORT=9090 python operator_dashboard/dashboard_server.py
```

On Windows PowerShell:

```powershell
$env:OPERATOR_DASHBOARD_PORT = "9090"
python operator_dashboard/dashboard_server.py
```

New dashboard accounts are created as `pending`. Keep the dashboard terminal open and approve users with:

```text
pending
approve <username>
reject <username>
```

Only approved operators can log in.

## TLS and Certificate Configuration

TLS is configured in `server/core/tls_context.py`.

The active configuration values are in `server/config/server_config.py`:

```python
HOST = "0.0.0.0"
PORT = 8443

SERVER_CERT = "certs/server.crt"
SERVER_KEY = "certs/server.key"
CA_CERT = "certs/ca.crt"
```

The server creates a default SSL context for client authentication:

- `ssl.Purpose.CLIENT_AUTH`
- `context.verify_mode = ssl.CERT_REQUIRED`
- server certificate loaded from `certs/server.crt`
- server private key loaded from `certs/server.key`
- client certificate trust loaded from `certs/ca.crt`

The certificate SAN config in `certs/server_san.cnf` and `server/config/server_san.cnf` currently identifies:

- Organization: `EcoGrid`
- Common Name: `13.61.12.216`
- SAN IP addresses: `13.61.12.216`, `127.0.0.1`

Do not publish or share the private keys in `certs/*.key` or `server/config/*.key`.

## IEEE 2030.5 Endpoints

Routes are defined in `server/core/router.py`.

| Method | Path | Handler | Purpose |
| --- | --- | --- | --- |
| `GET` | `/dcap` | `handle_dcap` | Returns DeviceCapability XML with links to device, time, end-device list, and function-set assignments. |
| `GET` | `/edev/<id>` | `handle_end_device` | Returns an EndDevice XML resource with fixed sFDI/lFDI values and a DER list link. |
| `GET` | `/edev/<id>/der` | `handle_der` | Returns a DER XML resource pointing to `/derp`. |
| `GET` | `/derp` | `handle_der_program` | Returns a DERProgramList with program `DERP1` and control list link `/derp/1/derc`. |
| `GET` | `/derp/<program_id>/derc` | `handle_derc_list` | Returns latest active generated DER control for the program, or `204 No Content`. |
| `POST` | `/mup` | `handle_mup` | Accepts XML meter data, stores it in SQLite, and triggers control evaluation. |
| `GET` | `/mup_read` | `handle_get_mup` | Returns the latest row from `mup_log` as XML. |

Unknown paths return `404`.

## Endpoint Details

### `GET /dcap`

Returns:

```xml
<DeviceCapability xmlns="urn:ieee:std:2030.5:ns">
  <selfDeviceLink>/edev/1</selfDeviceLink>
  <endDeviceListLink>/edev</endDeviceListLink>
  <timeLink>/time</timeLink>
  <functionSetAssignmentsListLink>/fsa</functionSetAssignmentsListLink>
</DeviceCapability>
```

Note: `/time`, `/fsa`, and `/edev` list routes are advertised but are not currently implemented in `router.py`.

### `GET /edev/<id>`

Returns a static EndDevice resource:

```xml
<EndDevice xmlns="urn:ieee:std:2030.5:ns">
  <sFDI>111111111111</sFDI>
  <lFDI>AAAAAAAAAAAAAAAAAAAA</lFDI>
  <DERListLink>/edev/{device_id}/der</DERListLink>
</EndDevice>
```

### `GET /edev/<id>/der`

Returns:

```xml
<DER xmlns="urn:ieee:std:2030.5:ns">
  <DERProgramListLink>/derp</DERProgramListLink>
</DER>
```

### `GET /derp`

Returns:

```xml
<DERProgramList xmlns="urn:ieee:std:2030.5:ns">
  <DERProgram>
    <mRID>DERP1</mRID>
    <DERControlListLink>/derp/1/derc</DERControlListLink>
  </DERProgram>
</DERProgramList>
```

### `GET /derp/<program_id>/derc`

The server reads the newest active control for the requested program from `der_controls`.

If no active control exists:

```text
204 No Content
```

If a control exists, it returns a `DERControlList` containing:

- `mRID`
- `creationTime`
- `interval/start`
- `interval/duration`, currently `300` seconds
- `opModFixedVar` when reactive power setpoint exists
- `opModFixedW` when active power setpoint exists
- `DERControlExt/targetPhase`

### `POST /mup`

Accepts XML containing these fields, with or without XML namespaces:

```xml
<Metering>
  <voltage_a>231.5</voltage_a>
  <voltage_b>229.8</voltage_b>
  <voltage_c>242.1</voltage_c>
  <power_a>1200</power_a>
  <power_b>1100</power_b>
  <power_c>1250</power_c>
  <reactive_a>50</reactive_a>
  <reactive_b>40</reactive_b>
  <reactive_c>55</reactive_c>
  <frequency>50.0</frequency>
</Metering>
```

The handler:

1. Reads the request body.
2. Parses XML with `xml.etree.ElementTree`.
3. Converts missing or invalid values to `0.0`.
4. Stores the measurement in `mup_log`.
5. Calculates `total_pv_power` as `power_a + power_b + power_c`.
6. Immediately calls `evaluate_and_create_event()`.
7. Returns `200` on success or `500` on parsing/storage errors.

### `GET /mup_read`

Reads the latest `mup_log` row and returns:

```xml
<Metering>
  <voltage_a>...</voltage_a>
  <voltage_b>...</voltage_b>
  <voltage_c>...</voltage_c>
  <power_a>...</power_a>
  <power_b>...</power_b>
  <power_c>...</power_c>
  <reactive_a>...</reactive_a>
  <reactive_b>...</reactive_b>
  <reactive_c>...</reactive_c>
  <frequency>...</frequency>
</Metering>
```

If there is no measurement, it returns `204 No Content`.

## Control Engine

The control engine lives in:

- `server/control_engine/control_logic.py`
- `server/control_engine/ieee1547_controller.py`

There are two trigger paths:

- Every `POST /mup` immediately evaluates the newest measurement.
- The background loop in `server/main.py` evaluates the newest measurement every 5 seconds.

The active logic reads the latest row:

```sql
SELECT voltage_a, voltage_b, voltage_c, total_pv_power
FROM mup_log
ORDER BY id DESC LIMIT 1
```

It then checks three-phase voltage:

- If maximum phase voltage is greater than `240 V`, condition is `OVER_VOLTAGE`.
- If minimum phase voltage is less than `220 V`, condition is `UNDER_VOLTAGE`.
- Otherwise, no control is generated.

The phase with the highest or lowest triggering voltage becomes `target_phase`.

### IEEE 1547-Style Curves

`server/control_engine/ieee1547_controller.py` uses nominal voltage:

```python
V_NOM = 230.0
```

Volt-VAR curve:

```python
VV_X = [0.92, 0.98, 1.02, 1.08]
VV_Y = [1.0, 0.0, 0.0, -1.0]
```

Volt-Watt curve:

```python
VW_X = [1.06, 1.10, 1.15]
VW_Y = [1.0, 0.8, 0.0]
```

Control mode selection:

- `VV_VW` when voltage is above `1.10 pu`.
- `VV` when voltage is above `1.02 pu` or below `0.98 pu`.
- `NONE` otherwise.

Reactive power limit:

```python
Q_MAX = 6000
```

When mode is `VV`, the server creates:

- `q_set = int(volt_var(V) * Q_MAX)`
- `p_set = 0`

When mode is `VV_VW`, the server creates:

- `q_set = int(volt_var(V) * Q_MAX)`
- `p_set = int(total_pv_power * volt_watt(V))`

The generated control is inserted into `der_controls` with:

- `mrid`, formatted as `CTRL<unix_timestamp>`
- `program_id`, currently `1`
- `created_at`, unix timestamp
- `q_set`
- `p_set`
- `target_phase`
- `condition`
- `active = 1`

## Database

The active SEP database is:

```text
server/database/ieee2030.db
```

The database helper is `server/database/database.py`. It provides:

- `get_connection()`
- `query(sql, params=(), one=False)`
- `execute(sql, params=())`
- `get_ders()`
- `get_programs()`
- `get_default_control()`
- `get_program(program_id)`
- `initialize_database()`

The current database contains these tables:

| Table | Purpose | Current row count at inspection |
| --- | --- | --- |
| `mup_log` | Main telemetry log used by the control engine and dashboard charts. | `5267` |
| `der_controls` | Generated DER control events served by `/derp/<program_id>/derc`. | `4892` |
| `der_programs` | Program metadata table; currently not used by the static `/derp` response. | `0` |
| `end_devices` | Device metadata table; currently not used by static `/edev/<id>` response. | `0` |
| `measurements` | Older/simple measurement table not used by current MUP handler. | `10` |
| `event_status` | Intended status table for control events. | `0` |

### `mup_log`

```sql
CREATE TABLE mup_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  voltage_a REAL,
  voltage_b REAL,
  voltage_c REAL,
  total_pv_power REAL,
  power_a REAL,
  power_b REAL,
  power_c REAL,
  reactive_a REAL,
  reactive_b REAL,
  reactive_c REAL,
  frequency REAL
);
```

### `der_controls`

```sql
CREATE TABLE der_controls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mrid TEXT,
  program_id INTEGER,
  created_at INTEGER,
  q_set REAL,
  active INTEGER,
  target_phase INTEGER,
  p_set REAL,
  condition TEXT
);
```

### `der_programs`

```sql
CREATE TABLE der_programs (
  id INTEGER PRIMARY KEY,
  name TEXT,
  active INTEGER
);
```

### `end_devices`

```sql
CREATE TABLE end_devices (
  id INTEGER PRIMARY KEY,
  sfdi TEXT,
  lfdi TEXT,
  registered INTEGER
);
```

### `measurements`

```sql
CREATE TABLE measurements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp INTEGER,
  voltage_a REAL,
  voltage_b REAL,
  voltage_c REAL,
  power REAL
);
```

### `event_status`

```sql
CREATE TABLE event_status (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  control_mrid TEXT,
  status TEXT
);
```

## Operator Dashboard

The dashboard runs from `operator_dashboard/dashboard_server.py`.

It uses:

- `operator_dashboard/data/operators.db` for dashboard users.
- `server/database/ieee2030.db` for SEP server data.
- `server_runtime.log` for runtime events.
- `dashboard_started_sep.log` for SEP server output when started from the dashboard.

Dashboard pages:

| Path | Purpose |
| --- | --- |
| `/login` | Operator login. |
| `/register` | Operator registration; accounts wait for terminal approval. |
| `/dashboard` | Live SEP status, voltages, power, frequency, logs, and start/stop controls. |
| `/tables` | Read-only table browser for the SEP SQLite database. |
| `/logs` | Runtime log viewer. |
| `/clients` | Client request summary inferred from logs. |
| `/api/status` | JSON server-running status. |
| `/api/live` | JSON payload for live dashboard refresh. |
| `/logout` | Ends the dashboard session. |

The browser polls `/api/live` every 2 seconds. `operator_dashboard/static/dashboard.js` draws charts directly with the HTML canvas API.

Dashboard authentication uses:

- PBKDF2-HMAC-SHA256 password hashes.
- Per-user random salts.
- In-memory session IDs stored in an `HttpOnly` cookie.
- Account statuses: `pending`, `approved`, `rejected`.

The dashboard is useful for development and operations, but it is served over plain HTTP by default. Put it behind HTTPS and stronger access control before exposing it to an untrusted network.

## Logging

`server/utils/runtime_logger.py` configures logging to:

- stdout
- `server_runtime.log`

The log format is:

```text
YYYY-MM-DD HH:MM:SS,mmm [LEVEL] message
```

The request handler logs each request as:

```text
GET request from <client-ip> -> <path>
POST request from <client-ip> -> <path>
PUT request from <client-ip> -> <path>
```

The dashboard uses those lines to infer client activity.

## LFDI and SFDI Helpers

There are two helper implementations:

Top-level `security/lfdi.py`:

- `generate_lfdi(cert_pem: str)`: SHA-256 hash of PEM text, first 32 hex characters, uppercase.
- `generate_sfdi(lfdi: str)`: last 8 characters of the LFDI.

Server package `server/security/lfdi.py`:

- `generate_lfdi(cert_bin)`: SHA-256 hash of certificate bytes, first 40 hex characters, uppercase.
- `generate_sfdi(lfdi)`: converts LFDI hex to integer and returns the last 9 decimal digits.

The active routing path does not currently call these helpers. The served `/edev/<id>` response uses static placeholder values.

## Example Client Calls

Because the server requires mutual TLS, a client request must include a trusted client certificate and key.

Example with `curl`:

```bash
curl -k \
  --cert certs/client.crt \
  --key certs/client.key \
  --cacert certs/ca.crt \
  https://127.0.0.1:8443/dcap
```

Post a measurement:

```bash
curl -k \
  --cert certs/client.crt \
  --key certs/client.key \
  --cacert certs/ca.crt \
  -H "Content-Type: application/xml" \
  -d "<Metering><voltage_a>231</voltage_a><voltage_b>229</voltage_b><voltage_c>242</voltage_c><power_a>1200</power_a><power_b>1100</power_b><power_c>1250</power_c><reactive_a>50</reactive_a><reactive_b>40</reactive_b><reactive_c>55</reactive_c><frequency>50</frequency></Metering>" \
  https://127.0.0.1:8443/mup
```

Read the latest measurement:

```bash
curl -k \
  --cert certs/client.crt \
  --key certs/client.key \
  --cacert certs/ca.crt \
  https://127.0.0.1:8443/mup_read
```

Read DER controls:

```bash
curl -k \
  --cert certs/client.crt \
  --key certs/client.key \
  --cacert certs/ca.crt \
  https://127.0.0.1:8443/derp/1/derc
```

## Important Implementation Notes

- `server/config/server_config.py` defines `DB_PATH = "database/ieee2030.db"`, but `server/database/database.py` actually uses `server/database/ieee2030.db` based on its own file location. The database helper is the effective source of truth.
- `initialize_database()` creates a smaller baseline schema than the current database file contains. The active code expects the extended `mup_log` columns: phase power, reactive power, and frequency.
- `/dcap` advertises `/time`, `/fsa`, and `/edev`, but only `/edev/<id>` is implemented.
- `/derp` returns static XML instead of reading `der_programs`.
- `/edev/<id>` returns static sFDI/lFDI instead of reading `end_devices`.
- Generated controls are inserted with `active = 1`, and there is no current route that deactivates old controls.
- The dashboard can stop only a SEP process it started directly, except on POSIX systems where it attempts `pkill -f "python.*-m server.main"`.
- The dashboard reads the database in read-only mode for display.

## Suggested Development Workflow

1. Start the dashboard:

   ```bash
   python operator_dashboard/dashboard_server.py
   ```

2. Register an operator at `http://localhost:8080/register`.
3. Approve the operator in the dashboard terminal.
4. Log in at `http://localhost:8080/login`.
5. Start the SEP server from the dashboard or run:

   ```bash
   python -m server.main
   ```

6. Send mTLS client requests to `https://127.0.0.1:8443`.
7. Watch live measurements, logs, generated controls, and client activity in the dashboard.

## Security Notes

- Treat all `.key` files as secrets.
- Replace development certificates before production use.
- Keep the CA private key offline or restricted.
- Do not expose the dashboard over public HTTP.
- Add authorization/ACL checks before accepting untrusted DER clients, because the current server relies primarily on mTLS trust.
- Consider rotating dashboard sessions on privilege changes and setting secure cookies when served over HTTPS.

## Current Project State

This is an active development server. The core request flow, MUP ingestion, control generation, mTLS wrapping, logging, dashboard authentication, and dashboard visualization are implemented. Some IEEE 2030.5 resources are intentionally simplified or static and should be expanded if full SEP conformance is required.

