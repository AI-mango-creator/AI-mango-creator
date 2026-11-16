-- 只修复T13中曾将设备UUID编码进ID的owned记录；legacy原ID不变。
-- 延迟现有外键检查，使父子ID在同一事务完成映射；不DROP、不丢失引用。
PRAGMA defer_foreign_keys = ON;

UPDATE wardrobe_items SET id=opaque_item_id(owner_id, id)
WHERE owner_id!='legacy' AND
      (id LIKE replace(owner_id, '-', '') || ':%' OR id LIKE 'U' || replace(owner_id, '-', '') || '%');

UPDATE outfit_items SET item_id=opaque_item_id(owner_id, item_id)
WHERE owner_id!='legacy' AND
      (item_id LIKE replace(owner_id, '-', '') || ':%' OR item_id LIKE 'U' || replace(owner_id, '-', '') || '%');
