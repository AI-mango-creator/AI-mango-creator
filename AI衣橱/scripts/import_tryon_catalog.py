"""本地有权体验素材导入；默认dry-run，不自动获取平台商品。"""
import argparse
import hashlib
import json
import shutil
from contextlib import closing
from pathlib import Path
from time import time

from app.db import DB_PATH, connect_db, init_db, to_db_values
from app.models import ExperienceProduct
from app.services.community import _image


def import_catalog(manifest, path=DB_PATH, *, apply=False):
    manifest, path = Path(manifest).resolve(), Path(path).resolve()
    rows = json.loads(manifest.read_text())
    if not isinstance(rows, list):
        raise TypeError('素材清单必须是数组。')
    checked, ids = [], set()
    for row in rows:
        try:
            photo = (manifest.parent/row['photo']).resolve()
            data = photo.read_bytes()
            _, ext = _image(data)
            values = {k: row[k].strip() for k in ('id', 'title', 'category', 'source_label', 'rights_note')}
            digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()+data).hexdigest()
            item = ExperienceProduct(**values, image_path=f'uploads/catalog/{values["id"]}/image{ext}', content_hash=digest, created_at=time())
            if item.id in ids:
                raise ValueError('素材ID重复。')
            ids.add(item.id)
            checked.append((item, data))
        except Exception as exc:
            # CLI always exposes a readable local validation error, never input image bytes.
            raise ValueError('素材无效，请检查图片、ID、类别、来源与使用权说明。') from exc
    inserted = 0
    if apply:
        init_db(path)
        with closing(connect_db(path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            for item, _ in checked:
                old = db.execute('SELECT content_hash FROM experience_products WHERE id=?', (item.id,)).fetchone()
                if old and old[0] != item.content_hash:
                    raise ValueError('相同ID已存在不同素材，禁止覆盖。')
            created = []
            try:
                for item, data in checked:
                    if db.execute('SELECT 1 FROM experience_products WHERE id=?', (item.id,)).fetchone():
                        continue
                    target = path.parent/item.image_path
                    target.parent.mkdir(parents=True, exist_ok=False)
                    created.append(target.parent)
                    target.write_bytes(data)
                    values = to_db_values(item)
                    db.execute(f"INSERT INTO experience_products ({','.join(values)}) VALUES ({','.join(':'+k for k in values)})", values)
                    inserted += 1
            except Exception:
                for directory in created:
                    shutil.rmtree(directory)
                raise
    return {'checked': len(checked), 'inserted': inserted}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--db', type=Path, default=DB_PATH)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(import_catalog(args.manifest, args.db, apply=args.apply), ensure_ascii=False))
    except (ValueError, TypeError) as exc:
        parser.exit(2, str(exc)+'\n')


if __name__ == '__main__':
    main()
