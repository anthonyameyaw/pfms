# 🌴 Palm Farm Management System (PFMS)

A local web application for managing palm farm activities, harvests, 
processing plant operations, finances, and market price intelligence.

**Covers:** 6 farms in Nkrankwanta & Kuren (Dormaa West / Dormaa Central) 
plus the Nkrankwanta processing plant.

---

## Quickstart (First Time)

### Step 1 — Install Python 3

Check if you have it:
```
python3 --version
```
If not installed, download from: https://www.python.org/downloads/

### Step 2 — Install Flask

Open Terminal, navigate to this folder, then run:
```
pip3 install -r requirements.txt
```

### Step 3 — Start the App

Double-click `start.sh`, or in Terminal:
```
./start.sh
```

The app will open automatically in your browser at **http://localhost:5000**

---

## Daily Use

Every time you want to use the app:
1. Open Terminal
2. `cd` to the pfms folder
3. Run `./start.sh`
4. Go to http://localhost:5000 in your browser
5. Press `Ctrl+C` in Terminal to stop when done

---

## What's Inside

| Section | What it does |
|---------|-------------|
| **Dashboard** | Monthly/YTD P&L snapshot, alerts, quick actions |
| **Farms** | Profile and detail view for each of the 6 farms |
| **Activities** | Log all farm work — weeding, spraying, maintenance, etc. |
| **Harvests** | Record bunches harvested; view forecast per farm |
| **Pruning** | Track pruning batches and 6-month cycle completion |
| **Processing Plant** | Log processing runs (auto-calculates all financials) |
| **Transport** | Pickup trips, tricycle rentals, vehicle maintenance |
| **Finances** | Consolidated P&L — all farms + plant combined |
| **Price Tracker** | Log FFB/palm oil prices with negotiation outcomes |
| **Labour Intel** | Average cost per activity type for negotiation |
| **Reports & Export** | Per-farm P&L report + CSV exports for all data |

---

## Processing Plant Formula

When you log a processing run (enter output in litres), the system automatically calculates:

| Formula | |
|---------|--|
| Gallons | Litres ÷ 25 |
| Gross Revenue | Gallons × GHS 40 |
| Electricity Cost | (Gallons ÷ 20) × GHS 120 |
| Net Revenue | Gross − Electricity |
| Operator Pay | Net × 30% |
| Company Revenue | Net × 70% |

Outside farmer fees are entered separately (GHS 40 per gallon from their fruits).

---

## Pruning Cycles

- Set the **total trees** count in each farm's profile
- Each time labourers prune a batch, log it under Pruning → Log Batch
- The system accumulates progress across batches
- When all trees are pruned, the cycle closes automatically
- A new cycle becomes due **6 months** later
- The Dashboard alerts you when a cycle is overdue

---

## Data & Backups

All data is stored in: `database/pfms.db`

To back up your data, simply copy the `pfms.db` file to a safe location 
(external drive, Google Drive, etc.). Recommended: weekly backup.

---

## Farms Reference

| ID | Name | Location | Size | Crop | Status |
|----|------|----------|------|------|--------|
| F1 | Cashew Farm | Kuren, Dormaa Central | 7 acres | Cashew | Active |
| F2 | Palm Farm A | Nkrankwanta, Dormaa West | 10 acres | Oil Palm | Inactive |
| F3 | Palm Farm B | Nkrankwanta, Dormaa West | 10.5 acres | Oil Palm | Development |
| F4 | Palm Farm C | Nkrankwanta, Dormaa West | 12 acres | Oil Palm | Active |
| F5 | Palm Farm D | Nkrankwanta, Dormaa West | 10 acres | Oil Palm | Active |
| F6 | Palm Farm E | Nkrankwanta, Dormaa West | 10 acres | Oil Palm | Active |

---

*Built for Anthony · May 2026*
