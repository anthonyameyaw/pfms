-- Empty fixture matching the migrated schema reviewed for finding 1.
CREATE TABLE farms (
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
CREATE TABLE activities (
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
CREATE TABLE harvests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id             INTEGER REFERENCES farms(id) ON DELETE CASCADE,
    activity_id         INTEGER REFERENCES activities(id) ON DELETE SET NULL,
    date                DATE NOT NULL,
    bunches_harvested   INTEGER DEFAULT 0,
    weight_tonnes       REAL,
    num_labourers       INTEGER DEFAULT 0,
    harvesting_cost     REAL DEFAULT 0,
    notes               TEXT
, harvester_pay REAL DEFAULT 0, collector_pay REAL DEFAULT 0, num_collectors INTEGER DEFAULT 0, gallons_produced REAL DEFAULT 0, price_per_gallon REAL DEFAULT 0, oil_income REAL DEFAULT 0, transport_mode TEXT DEFAULT NULL, driver_pay REAL DEFAULT 0, fuel_cost REAL DEFAULT 0, tricycle_rent REAL DEFAULT 0, gallons_sold REAL DEFAULT 0, husks_processed INTEGER DEFAULT NULL, gallons_sold_price REAL DEFAULT 0, gallons_sold_income REAL DEFAULT 0, threshing_cost REAL DEFAULT 0);
CREATE TABLE pruning_cycles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id             INTEGER REFERENCES farms(id) ON DELETE CASCADE,
    cycle_start_date    DATE NOT NULL,
    cycle_end_date      DATE,
    total_trees_pruned  INTEGER DEFAULT 0,
    is_complete         INTEGER DEFAULT 0,  -- 0=false, 1=true
    next_due_date       DATE
);
CREATE TABLE pruning_batches (
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
CREATE TABLE farm_income (
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
CREATE TABLE farm_expenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id         INTEGER REFERENCES farms(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    category        TEXT CHECK(category IN ('Labour','Materials','Transport','Other')),
    description     TEXT,
    amount          REAL DEFAULT 0,
    notes           TEXT
);
CREATE TABLE processing_run_farms (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER REFERENCES processing_runs(id) ON DELETE CASCADE,
    farm_id             INTEGER REFERENCES farms(id) ON DELETE CASCADE,
    bunches_contributed INTEGER DEFAULT 0
);
CREATE TABLE plant_expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        DATE NOT NULL,
    category    TEXT CHECK(category IN ('Maintenance','Casual Labour','Consumables','Other')),
    description TEXT,
    amount      REAL DEFAULT 0,
    notes       TEXT
);
CREATE TABLE transport_logs (
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
CREATE TABLE pickup_maintenance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        DATE NOT NULL,
    description TEXT,
    cost        REAL DEFAULT 0,
    notes       TEXT
);
CREATE TABLE price_log (
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
CREATE TABLE outside_farmers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT,
    location    TEXT,
    notes       TEXT
);
CREATE TABLE storage (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date_updated     DATE NOT NULL,
            gallons_in_stock REAL DEFAULT 0,
            price_per_gallon REAL DEFAULT 0,
            total_value      REAL DEFAULT 0,
            notes            TEXT
        );
CREATE TABLE processing_runs (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    date                        DATE NOT NULL,
    own_farms_litres            REAL DEFAULT 0,
    own_farms_gallons           REAL DEFAULT 0,
    own_farms_bunches           INTEGER DEFAULT 0,
    outside_farmers_litres      REAL DEFAULT 0,
    outside_farmers_gallons     REAL DEFAULT 0,
    outside_farmers_bunches     INTEGER DEFAULT 0,
    total_output_litres         REAL DEFAULT 0,
    total_output_gallons        REAL DEFAULT 0,
    gross_revenue               REAL DEFAULT 0,
    outside_farmer_fees         REAL DEFAULT 0,
    electricity_cost            REAL DEFAULT 0,
    net_revenue                 REAL DEFAULT 0,
    operator_pay                REAL DEFAULT 0,
    company_revenue             REAL DEFAULT 0,
    cash_collected              REAL DEFAULT 0,
    cash_outstanding            REAL DEFAULT 0,
    notes                       TEXT
);
CREATE TABLE investors (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        phone       TEXT,
        email       TEXT,
        location    TEXT,
        notes       TEXT,
        date_joined DATE
    );
CREATE TABLE investments (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        investor_id     INTEGER NOT NULL REFERENCES investors(id) ON DELETE CASCADE,
        farm_id         INTEGER REFERENCES farms(id),
        date            DATE NOT NULL,
        amount          REAL NOT NULL DEFAULT 0,
        investment_type TEXT DEFAULT 'Cash',
        equity_pct      REAL DEFAULT 0,
        expected_return REAL DEFAULT 0,
        return_date     DATE,
        status          TEXT DEFAULT 'Active',
        notes           TEXT
    , return_pct REAL DEFAULT 0);
CREATE TABLE investor_returns (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        investor_id   INTEGER NOT NULL REFERENCES investors(id),
        investment_id INTEGER REFERENCES investments(id),
        date          DATE NOT NULL,
        amount        REAL DEFAULT 0,
        notes         TEXT
    );
CREATE TABLE "storage_transactions" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    gallons REAL DEFAULT 0,
    price_per_gallon REAL DEFAULT 0,
    reason TEXT,
    notes TEXT,
    farm_id INTEGER,
    fresh_gallons REAL DEFAULT 0,
    soap_gallons REAL DEFAULT 0,
    seller TEXT,
    buyer TEXT,
    total_amount REAL DEFAULT 0
);
