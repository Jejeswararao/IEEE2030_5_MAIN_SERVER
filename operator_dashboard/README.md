# IEEE 2030.5 Operator Dashboard

Standalone operator web dashboard for the existing SEP server.

This dashboard does not modify the existing server code. It runs as a separate
control-plane web app and can:

- register/login operators
- keep registrations pending until terminal approval
- start `python3 -m server.main` when it is not running
- stop `python3 -m server.main`
- show server status
- show recent runtime logs
- list SQLite tables from `server/database/ieee2030.db`
- show recent measurement/client activity
- update live dashboard cards and charts without browser reloads

## Run

From the project root:

```bash
python3 operator_dashboard/dashboard_server.py
```

Open:

```text
http://<ec2-public-ip>:8080/login
```

The IEEE 2030.5 server still runs on port `8443`.

## Operator Approval

New registrations are not active immediately. Keep the dashboard terminal open.
When someone registers, the terminal prints an approval prompt.

Available terminal commands:

```text
pending
approve <username>
reject <username>
```

Only approved operators can log in.

## Notes

The dashboard must run separately from the SEP server if it needs to start the
SEP server. A stopped server cannot also serve the website that starts it.

For same public port access, use a reverse proxy such as Nginx later:

- `/dashboard/` -> dashboard app
- IEEE 2030.5 paths -> `server.main` on 8443
