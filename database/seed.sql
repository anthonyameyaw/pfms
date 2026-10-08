-- Starter farms, inserted only for a fresh database.
INSERT OR IGNORE INTO farms (id, name, location, constituency, size_acres, crop_type, status, total_trees, notes) VALUES
(1, 'Cashew Farm',   'Kuren',        'Dormaa Central', 7.0,  'Cashew',   'Active',      0,    'Cashew farm — activity tracking only'),
(2, 'Palm Farm A',   'Nkrankwanta',  'Dormaa West',    10.0, 'Oil Palm', 'Inactive',    0,    'Needs revival investment — not producing'),
(3, 'Palm Farm B',   'Nkrankwanta',  'Dormaa West',    10.5, 'Oil Palm', 'Development', 0,    'Under development — planting phase'),
(4, 'Palm Farm C',   'Nkrankwanta',  'Dormaa West',    12.0, 'Oil Palm', 'Active',      0,    'Active producing farm'),
(5, 'Palm Farm D',   'Nkrankwanta',  'Dormaa West',    10.0, 'Oil Palm', 'Active',      0,    'Active producing farm'),
(6, 'Palm Farm E',   'Nkrankwanta',  'Dormaa West',    10.0, 'Oil Palm', 'Active',      0,    'Active producing farm');
