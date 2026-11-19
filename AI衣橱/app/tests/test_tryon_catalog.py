import json
from contextlib import closing
from pathlib import Path

import pytest

from app.db import connect_db
from scripts.import_tryon_catalog import import_catalog

PHOTO=Path(__file__).resolve().parents[2]/'cases/images/cloth01.jpg'


def test_dry_run_import_rights_and_idempotency(tmp_path):
    manifest=tmp_path/'manifest.json';path=tmp_path/'data/app.db'
    item={'id': 'test-top','title': '测试上装','category': 'tops','photo': str(PHOTO),'source_label': '测试夹具，非商品合作','rights_note': '仅离线测试'}
    manifest.write_text(json.dumps([item]))
    assert import_catalog(manifest,path)=={'checked':1,'inserted':0}
    assert not path.exists()
    assert import_catalog(manifest,path,apply=True)=={'checked':1,'inserted':1}
    assert import_catalog(manifest,path,apply=True)=={'checked':1,'inserted':0}
    with closing(connect_db(path)) as db:
        assert db.execute('select count(*) from wardrobe_items').fetchone()[0]==0
        assert db.execute('select owner_id from experience_products').fetchone()[0]=='catalog'
    for changes in [{'title': '不同内容'},{'rights_note': ''},{'photo': str(manifest)}]:
        manifest.write_text(json.dumps([item|changes]))
        with pytest.raises(ValueError):import_catalog(manifest,path,apply=True)
