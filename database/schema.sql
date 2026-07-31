-- Palm Farm Management System (PFMS)
-- Database Schema
-- SQLite

PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────
-- TABLE 1: farms
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS farms (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    location        TEXT,
    constituency    TEXT,
    size_acres      REAL,
    crop_type       TEXT CHECK(crop_type IN ('Oil Palm', 'Cashew')),
    status          TEXT CHECK(status IN ('Active', 'Inactive', 'Development')),
    total_trees     INTEGER DEFAULT 0,
    notes           TEXT,
    created_at      DATE DEFAULT (DATE('now'))
);

-- ─────────────────────────────────────────
-- TABLE 2: activities
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS activities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id         INTEGER REFERENCES farms(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    activity_type   TEXT CHECK(activity_type IN (
                        'Harvesting','Weeding','Fertilising','Spraying',
                        'Pruning','Planting','Maintenance','Other'
                    )),
    description     TEXT,
    num_labourers   INTEGER DEFAULT 0,
    labour_cost     REAL DEFAULT 0,
    materials_used  TEXT,
    materials_cost  REAL DEFAULT 0,
    total_cost      REAL GENERATED ALWAYS AS (labour_cost + materials_cost) STORED,
    notes           TEXT
);

-- ─────────────────────────────────────────
-- TABLE 3: harvests
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS harvests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id             INTEGER REFERENCES farms(id) ON DELETE CASCADE,
    activity_id         INTEGER REFERENCES activities(id) ON DELETE SET NULL,
    date                DATE NOT NULL,
    bunches_harvested   INTEGER DEFAULT 0,
    weight_tonnes       REAL,
    num_labourers       INTEGER DEFAULT 0,
    harvesting_cost     REAL DEFAULT 0,
    notes               TEXT
);

-- ─────────────────────────────────────────
-- TABLE 4: pruning_cycles
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pruning_cycles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id             INTEGER REFERENCES farms(id) ON DELETE CASCADE,
    cycle_start_date    DATE NOT NULL,
    cycle_end_date      DATE,
    total_trees_pruned  INTEGER DEFAULT 0,
    is_complete         INTEGER DEFAULT 0,  -- 0=false, 1=true
    next_due_date       DATE
);

-- ─────────────────────────────────────────
-- TABLE 5: pruning_batches
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pruning_batches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id         INTEGER REFERENCES farms(id) ON DELETE CASCADE,
    activity_id     INTEGER REFERENCES activities(id) ON DELETE SET NULL,
    cycle_id        INTEGER REFERENCES pruning_cycles(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    trees_pruned    INTEGER DEFAULT 0,
    num_labourers   INTEGER DEFAULT 0,
    cost            REAL DEFAULT 0,
    notes           TEXT
);

-- ─────────────────────────────────────────
-- TABLE 6: farm_income
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS farm_income (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id         INTEGER REFERENCES farms(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    income_type     TEXT CHECK(income_type IN ('FFB Sale', 'Other')),
    buyer           TEXT,
    quantity        REAL DEFAULT 0,
    unit_price      REAL DEFAULT 0,
    total_amount    REAL GENERATED ALWAYS AS (quantity * unit_price) STORED,
    notes           TEXT
);

-- ─────────────────────────────────────────
-- TABLE 7: farm_expenses
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS farm_expenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id         INTEGER REFERENCES farms(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    category        TEXT CHECK(category IN ('Labour','Materials','Transport','Other')),
    description     TEXT,
    amount          REAL DEFAULT 0,
    notes           TEXT
);

-- ─────────────────────────────────────────
-- TABLE 8: processing_runs
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS processing_runs (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    date                    DATE NOT NULL,
    own_farms_bunches       INTEGER DEFAULT 0,
    outside_farmers_bunches INTEGER DEFAULT 0,
    total_output_litres     REAL DEFAULT 0,
    total_output_gallons    REAL GENERATED ALWAYS AS (total_output_litres / 25.0) STORED,
    gross_revenue           REAL GENERATED ALWAYS AS ((total_output_litres / 25.0) * 40.0) STORED,
    electricity_cost        REAL GENERATED ALWAYS AS (((total_output_litres / 25.0) / 20.0) * 120.0) STORED,
    net_revenue             REAL GENERATED ALWAYS AS (
                                ((total_output_litres / 25.0) * 40.0) -
                                (((total_output_litres / 25.0) / 20.0) * 120.0)
                            ) STORED,
    operator_pay            REAL GENERATED ALWAYS AS (
                                (
                                    ((total_output_litres / 25.0) * 40.0) -
                                    (((total_output_litres / 25.0) / 20.0) * 120.0)
                                ) * 0.30
                            ) STORED,
    company_revenue         REAL GENERATED ALWAYS AS (
                                (
                                    ((total_output_litres / 25.0) * 40.0) -
                                    (((total_output_litres / 25.0) / 20.0) * 120.0)
                                ) * 0.70
                            ) STORED,
    outside_farmer_fees     REAL DEFAULT 0,
    notes                   TEXT
);

-- ─────────────────────────────────────────
-- TABLE 9: processing_run_farms
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS processing_run_farms (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER REFERENCES processing_runs(id) ON DELETE CASCADE,
    farm_id             INTEGER REFERENCES farms(id) ON DELETE CASCADE,
    bunches_contributed INTEGER DEFAULT 0
);

-- ─────────────────────────────────────────
-- TABLE 10: plant_expenses
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS plant_expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        DATE NOT NULL,
    category    TEXT CHECK(category IN ('Maintenance','Casual Labour','Consumables','Other')),
    description TEXT,
    amount      REAL DEFAULT 0,
    notes       TEXT
);

-- ─────────────────────────────────────────
-- TABLE 11: transport_logs
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transport_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            DATE NOT NULL,
    transport_type  TEXT CHECK(transport_type IN ('Pickup','Tricycle')),
    farm_id         INTEGER REFERENCES farms(id) ON DELETE SET NULL,
    fuel_cost       REAL DEFAULT 0,
    driver_pay      REAL DEFAULT 0,
    rental_cost     REAL DEFAULT 0,
    total_cost      REAL GENERATED ALWAYS AS (fuel_cost + driver_pay + rental_cost) STORED,
    notes           TEXT
);

-- ─────────────────────────────────────────
-- TABLE 12: pickup_maintenance
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pickup_maintenance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        DATE NOT NULL,
    description TEXT,
    cost        REAL DEFAULT 0,
    notes       TEXT
);

-- ─────────────────────────────────────────
-- TABLE 13: price_log
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS price_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                DATE NOT NULL,
    product             TEXT CHECK(product IN ('FFB','Palm Oil')),
    buyer_source        TEXT,
    price_offered       REAL DEFAULT 0,
    price_accepted      REAL DEFAULT 0,
    unit                TEXT,
    negotiation_outcome TEXT CHECK(negotiation_outcome IN ('Accepted','Rejected','Countered')),
    notes               TEXT
);

-- ─────────────────────────────────────────
-- TABLE 14: outside_farmers
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS outside_farmers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT,
    location    TEXT,
    notes       TEXT
);

-- ─────────────────────────────────────────
-- SEED DATA: The 6 farms
-- ─────────────────────────────────────────
INSERT OR IGNORE INTO farms (id, name, location, constituency, size_acres, crop_type, status, total_trees, notes) VALUES
(1, 'Cashew Farm',   'Kuren',        'Dormaa Central', 7.0,  'Cashew',   'Active',      0,    'Cashew farm — activity tracking only'),
(2, 'Palm Farm A',   'Nkrankwanta',  'Dormaa West',    10.0, 'Oil Palm', 'Inactive',    0,    'Needs revival investment — not producing'),
(3, 'Palm Farm B',   'Nkrankwanta',  'Dormaa West',    10.5, 'Oil Palm', 'Development', 0,    'Under development — planting phase'),
(4, 'Palm Farm C',   'Nkrankwanta',  'Dormaa West',    12.0, 'Oil Palm', 'Active',      0,    'Active producing farm'),
(5, 'Palm Farm D',   'Nkrankwanta',  'Dormaa West',    10.0, 'Oil Palm', 'Active',      0,    'Active producing farm'),
(6, 'Palm Farm E',   'Nkrankwanta',  'Dormaa West',    10.0, 'Oil Palm', 'Active',      0,    'Active producing farm');

-- ─────────────────────────────────────────
-- TABLE 15: storage (current inventory snapshot)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS storage (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    date_updated     DATE NOT NULL,
    gallons_in_stock REAL DEFAULT 0,
    price_per_gallon REAL DEFAULT 0,
    total_value      REAL DEFAULT 0,
    notes            TEXT
);

-- ─────────────────────────────────────────
-- TABLE 16: storage_transactions
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS storage_transactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    date             DATE NOT NULL,
    transaction_type TEXT CHECK(transaction_type IN ('Addition','Removal','Revaluation')),
    gallons          REAL DEFAULT 0,
    price_per_gallon REAL DEFAULT 0,
    reason           TEXT,
    notes            TEXT
);
