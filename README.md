# Palm Farm Management System (PFMS)

A local Flask app for farm activities, harvests, oil storage and sales, processing runs, investors, finances and reports.

## Run locally

Use Python 3.12 and install the dependencies in a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python launcher.py
```

Open **http://127.0.0.1:5001**. The launcher checks dependencies, reuses an existing verified PFMS server, and refuses to replace another app using the port. Logs are in `.runtime/server.log`.

The existing macOS `launch_pfms.command` and `start.sh` shortcuts use the owner's configured Anaconda Python at `/Applications/anaconda3/bin/python3.12`. On other machines, use the virtual-environment command above. `python app.py` runs the server in the foreground; Ctrl+C stops it.

## Main sections

- **Dashboard:** overall and monthly finances, storage, weather, pending items and recent activity.
- **Farms and activities:** farm profiles, work, costs, pruning and transport.
- **Harvests:** production, harvesting and defruiting costs, linked transport and processing dates.
- **Processing plant:** farm contributions, outside processing, charges, expenses and cash collection.
- **Storage:** purchases, pooled oil inventory, sales and food/soap oil tracking.
- **Investors:** one summary per investor, investment history, expected returns and repayments.
- **Finances:** consolidated accounts, per-harvest levelized costs, farm averages and price planning.
- **Reports:** financial reports and CSV exports.

## Calculation conventions

One recorded **gallon means 25 litres**.

- Oil purchases are expensed when bought and added to inventory. Sales reduce inventory and record revenue.
- Own-farm processing charges are farm expenses and plant revenue; consolidated accounts eliminate these internal transfers.
- Harvest cost per gallon includes harvesting, defruiting, linked transport and linked processing fees. Pruning and general upkeep remain in the financial accounts but are excluded from this metric.
- Farm and combined harvest-cost averages divide matched harvest costs by their total processed gallons. They are weighted by output, not simple averages of harvest rates.
- Unknown plant cash collection is distinct from an explicit zero payment.
- Historical harvest costs do not include every business expense; account for excluded costs when planning a selling price.

## Data and upgrades

The live records are stored in `database/pfms.db`. This repository contains application source, schema, starter farm definitions and disposable test fixtures, **not the live database or private backups**. Fresh startup creates a database; existing databases are upgraded through versioned migrations.

Keep a separate database backup before upgrades. Stop the app before copying the database so the backup is consistent. Reports also provides exports. A GitHub source update is not a backup of farm records.

The app binds to the local device. Its session key is generated locally in `database/.session_secret`; do not commit it. Weather and external chart assets need internet access.

## Tests

```sh
python -B -m unittest discover -s tests -q
```

Tests use disposable databases. Older root-level `fix_*`, `patch_*`, `backfill_*` and diagnostic scripts are historical maintenance tools, not the startup or upgrade procedure; some can modify records.
