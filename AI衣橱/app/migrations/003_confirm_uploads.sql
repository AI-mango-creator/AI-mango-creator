-- D10-b一次性历史回填；运行时派生规则仅由models.py定义。
UPDATE wardrobe_items
SET needs_confirm=1, sources=json_set(sources, '$.needs_confirm', 'derived')
WHERE json_type(sources, '$._upload')='object' AND user_edited=0;
