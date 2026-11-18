ALTER TABLE wardrobe_items ADD COLUMN wardrobe_group TEXT
CHECK (wardrobe_group IS NULL OR wardrobe_group IN ('tops','bottoms','skirts','sets','shoes','bags','jewelry','accessories','unclassified'));
UPDATE wardrobe_items SET wardrobe_group = CASE
    WHEN category IN ('top','outer') THEN 'tops'
    WHEN category='dress' OR (category='bottom' AND sub LIKE '%裙%') THEN 'skirts'
    WHEN category='bottom' THEN 'bottoms'
    WHEN category='shoes' THEN 'shoes'
    WHEN category='accessory' THEN 'accessories'
    ELSE 'unclassified' END,
    sources=json_set(sources,'$.wardrobe_group','derived')
WHERE wardrobe_group IS NULL;
