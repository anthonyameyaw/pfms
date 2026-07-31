"""
Fix: when logging a pruning batch from the Pruning tab,
also write a record to the activities table so the cost
shows up in farm expenses everywhere.
"""

content = open('routes/pruning.py').read()

# Find the INSERT into pruning_batches and add an activities INSERT after it
# The pruning route saves to pruning_batches — we need to also save to activities

# Pattern: after inserting a pruning_batch, also insert into activities
# Find the execute that inserts into pruning_batches
import re

# Look for the add_batch POST handler
if 'pruning_batches' in content:
    # Find where pruning batch is inserted and add activities insert after
    old = """        execute(\"\"\"
            INSERT INTO pruning_batches
                (cycle_id, farm_id, date, trees_pruned, num_labourers,
                 labour_cost, notes)
            VALUES (?,?,?,?,?,?,?)
        \"\"\", (
            cycle_id,
            farm_id,
            date_val,
            trees_pruned,
            num_labourers,
            labour_cost,
            request.form.get('notes', ''),
        ))"""

    new = """        execute(\"\"\"
            INSERT INTO pruning_batches
                (cycle_id, farm_id, date, trees_pruned, num_labourers,
                 labour_cost, notes)
            VALUES (?,?,?,?,?,?,?)
        \"\"\", (
            cycle_id,
            farm_id,
            date_val,
            trees_pruned,
            num_labourers,
            labour_cost,
            request.form.get('notes', ''),
        ))

        # Also record in activities so cost flows through to farm P&L
        execute(\"\"\"
            INSERT INTO activities
                (farm_id, date, activity_type, description,
                 num_labourers, labour_cost, materials_used, materials_cost, notes)
            VALUES (?,?,?,?,?,?,?,?,?)
        \"\"\", (
            farm_id,
            date_val,
            'Pruning',
            f'Pruning batch — {trees_pruned} trees',
            num_labourers,
            labour_cost,
            '',
            0,
            request.form.get('notes', ''),
        ))"""

    if old in content:
        content = content.replace(old, new)
        open('routes/pruning.py', 'w').write(content)
        print("✅ Pruning batch now also writes to activities table")
    else:
        # Try to find the pattern more flexibly
        idx = content.find('INSERT INTO pruning_batches')
        if idx > 0:
            # Find the closing paren of the execute call
            end = content.find('\n\n', idx)
            snippet = content[idx-50:end+50]
            print("Pattern not found exactly. Found this near INSERT INTO pruning_batches:")
            print(repr(snippet[:500]))
        else:
            print("pruning_batches INSERT not found in pruning.py")
            print("First 200 chars:", repr(content[:200]))
else:
    print("'pruning_batches' not found in pruning.py")
    print("Route content preview:", repr(content[:300]))
