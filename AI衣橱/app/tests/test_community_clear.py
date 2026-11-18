from app.db import connect_db, reserve_quota
from app.tests.test_community_api import A, B, publish
from app.tests.test_community_api import community_api as _community_api

community_api = _community_api


def test_clear_withdraws_own_public_photos_keeps_others_and_quota(community_api):
    c, path = community_api
    mine = publish(c).json()
    other = publish(c, owner=B).json()
    reserve_quota(path, A, 'recognition')
    r = c.delete('/api/wardrobe/items')
    assert r.status_code == 200
    assert set(r.json()) == {'wardrobe_items', 'outfit_items', 'outfit_sets', 'sessions', 'photos'}
    posts = c.get('/api/community/posts', headers={'X-Device-ID': B}).json()['posts']
    assert [p['id'] for p in posts] == [other['id']]
    assert c.get(f"/api/community/posts/{mine['id']}/photos/{mine['media'][0]['id']}").status_code == 404
    with connect_db(path) as db:
        assert db.execute('select count(*) from community_authors where owner_id=?', (A,)).fetchone()[0] == 0
        assert db.execute('select sum(recognition) from daily_quotas').fetchone()[0] == 1
