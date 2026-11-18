import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app
from app.routers.wardrobe import database_path

A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
B = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
PHOTO = Path(__file__).resolve().parents[2] / 'cases/images/cloth01.jpg'


@pytest.fixture
def community_api(tmp_path):
    path = tmp_path / 'app.db'
    init_db(path)
    app.dependency_overrides[database_path] = lambda: path
    try:
        with TestClient(app, headers={'X-Device-ID': A}) as c:
            yield c, path
    finally:
        app.dependency_overrides.pop(database_path, None)


def publish(c, *, owner=A, kind='photo', draft=None, title='我的通勤穿搭', photos=1, **extra):
    values = dict(draft_id=draft or str(uuid4()), kind=kind, title=title, **extra)
    return c.post('/api/community/posts', headers={'X-Device-ID': owner},
                  data={'metadata': json.dumps(values)},
                  files=[('photos', ('photo.jpg', PHOTO.read_bytes(), 'image/jpeg')) for _ in range(photos)])


def test_real_cross_owner_feed_photo_privacy_and_idempotency(community_api):
    c, path = community_api
    assert c.get('/api/community/posts').status_code == 200
    draft = str(uuid4())
    r = publish(c, draft=draft)
    assert r.status_code == 201, r.text
    post = r.json()
    assert publish(c, draft=draft).json()['id'] == post['id']
    assert publish(c, draft=draft, title='另一标题').status_code == 409
    b = c.get('/api/community/posts', headers={'X-Device-ID': B}).json()['posts']
    assert [x['id'] for x in b] == [post['id']]
    assert b[0]['can_delete'] is False
    text = json.dumps(b)
    for secret in [A, B, 'owner_id', 'file_path', 'request_hash', 'item_ids']:
        assert secret not in text
    media = post['media'][0]['id']
    photo = c.get(f"/api/community/posts/{post['id']}/photos/{media}", headers={'X-Device-ID': B})
    assert photo.status_code == 200 and photo.content == PHOTO.read_bytes()
    assert photo.headers['x-content-type-options'] == 'nosniff'
    assert c.get('/api/wardrobe/items', headers={'X-Device-ID': B}).json() == []
    assert c.delete('/api/community/posts/'+post['id'], headers={'X-Device-ID': B}).status_code == 404
    assert c.delete('/api/community/posts/'+post['id']).status_code == 204
    assert c.get(f"/api/community/posts/{post['id']}/photos/{media}").status_code == 404
    assert c.delete('/api/community/posts/'+post['id']).status_code == 404
    assert not list((path.parent/'uploads/community').rglob('*.jpg'))


def test_all_post_types_and_validation(community_api):
    c, _ = community_api
    assert publish(c, kind='buy').status_code == 201
    poll = publish(c, kind='poll', photos=2, options=[{'label': '一号'}, {'label': '二号'}])
    assert poll.status_code == 201
    assert len(poll.json()['options']) == 2
    assert publish(c, kind='poll', options=[{'label': '一号'}, {'label': '二号'}]).status_code == 422
    assert publish(c, title=' ').status_code == 422
    assert publish(c, kind='outfit', photos=0, item_ids=['foreign1', 'foreign2']).status_code == 404
    assert c.get('/api/community/posts?tab=unknown').status_code == 400
    assert c.get('/api/community/posts?cursor=garbage').status_code == 400
    assert c.get('/api/community/posts', headers={'X-Device-ID': ''}).status_code == 400


def test_pagination_stable_and_invalid_media(community_api):
    c, _ = community_api
    ids = [publish(c).json()['id'] for _ in range(3)]
    first = c.get('/api/community/posts?limit=2').json()
    second = c.get('/api/community/posts', params={'limit': 2, 'cursor': first['next_cursor']}).json()
    assert [p['id'] for p in first['posts'] + second['posts']] == ids[::-1]
    values = {'draft_id': str(uuid4()), 'kind': 'photo', 'title': '测试'}
    r = c.post('/api/community/posts', data={'metadata': json.dumps(values)}, files={'photos': ('x.jpg', b'<html>', 'image/jpeg')})
    assert r.status_code == 422


def test_outfit_shares_only_own_explicit_copies(community_api):
    import shutil

    from app.db import connect_db
    from scripts.seed import seed_database
    c, path = community_api
    seed_database(path, owner_id=A)
    directory = path.parent/'uploads'/A
    directory.mkdir(parents=True)
    with connect_db(path) as db, db:
        ids = [x['id'] for x in db.execute('select id from wardrobe_items where owner_id=? limit 2', (A,))]
        for i, item_id in enumerate(ids):
            image = directory/f'{i}.jpg'
            shutil.copyfile(PHOTO, image)
            db.execute('update wardrobe_items set image_path=? where id=?', (str(image.relative_to(path.parent)), item_id))
    assert publish(c, kind='outfit', owner=B, photos=0, item_ids=ids).status_code == 404
    post = publish(c, kind='outfit', photos=0, item_ids=ids).json()
    assert len(post['media']) == 2
    assert all(item_id not in json.dumps(post) for item_id in ids)
    assert c.delete('/api/wardrobe/items/'+ids[0]).status_code == 204
    assert c.get(f"/api/community/posts/{post['id']}/photos/{post['media'][0]['id']}").status_code == 200


def test_deleted_post_cleanup_failure_is_retryable(community_api, monkeypatch):
    from app.services import community
    c, path = community_api
    post = publish(c).json()
    original = community.shutil.rmtree
    def fail(target, *args, **kw):
        if 'community_trash' in str(target):
            raise OSError('injected unlink failure')
        return original(target, *args, **kw)
    monkeypatch.setattr(community.shutil, 'rmtree', fail)
    r = c.delete('/api/community/posts/'+post['id'])
    assert r.status_code == 500 and '已撤回' in r.json()['detail']
    assert c.get('/api/community/posts').json()['posts'] == []
    assert list((path.parent/'uploads/community_trash').rglob('*.jpg'))
    monkeypatch.setattr(community.shutil, 'rmtree', original)
    assert c.delete('/api/community/posts/'+post['id']).status_code == 204
    assert not list((path.parent/'uploads/community_trash').rglob('*.jpg'))


def test_media_path_cannot_escape_public_post(community_api):
    from app.db import connect_db
    c, path = community_api
    post = publish(c).json()
    with connect_db(path) as db, db:
        db.execute('update community_media set file_path=? where id=?', ('app.db', post['media'][0]['id']))
    assert c.get(f"/api/community/posts/{post['id']}/photos/{post['media'][0]['id']}").status_code == 404


@pytest.mark.parametrize('data,mime', [(b'\xff\xd8\xff','image/jpeg'), (b'\x89PNG\r\n\x1a\n','image/png'), (b'RIFF\x04\x00\x00\x00WEBP','image/webp')])
def test_truncated_images_are_not_published(community_api, data, mime):
    c, path = community_api
    r = c.post('/api/community/posts', data={'metadata': json.dumps({'draft_id': str(uuid4()), 'kind': 'photo', 'title': '损坏图'})}, files={'photos': ('x', data, mime)})
    assert r.status_code == 422
    assert c.get('/api/community/posts').json()['posts'] == []
    assert not list((path.parent/'uploads/community').rglob('*.*'))


def test_publishing_with_relative_data_path_is_supported(tmp_path, monkeypatch):
    from app.models import CommunityDraft
    from app.services.community import publish as publish_service
    monkeypatch.chdir(tmp_path)
    path = Path('nested')/'app.db'
    init_db(path)
    p, reused = publish_service(path, A, CommunityDraft(draft_id=uuid4(), kind='photo', title='相对数据目录'), [PHOTO.read_bytes()])
    assert p.title == '相对数据目录' and not reused


def test_valid_png_and_webp_supported(community_api):
    import base64
    import struct
    import zlib

    def chunk(name, content):
        return struct.pack('>I', len(content))+name+content+struct.pack('>I', zlib.crc32(name+content))
    png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))+chunk(b'IDAT', zlib.compress(b'\x00\x00\x00\xff'))+chunk(b'IEND', b'')
    webp = base64.b64decode('UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA')
    c, _ = community_api
    for data, mime in [(png, 'image/png'), (webp, 'image/webp')]:
        r = c.post('/api/community/posts', data={'metadata': json.dumps({'draft_id': str(uuid4()), 'kind': 'photo', 'title': '有效照片'})}, files={'photos': ('x', data, mime)})
        assert r.status_code == 201, r.text
        p = r.json()
        image = c.get(f"/api/community/posts/{p['id']}/photos/{p['media'][0]['id']}")
        assert image.headers['content-type'] == mime
        assert image.content == data


def test_nested_webp_frames_rejected_without_recursion(community_api):
    # ANMF may contain ALPH/VP8/VP8L, never another ANMF.
    frame = b'VP8L'+(5).to_bytes(4, 'little')+b'\x2f\x00\x00\x00\x00\x00'
    for _ in range(1100):
        frame = b'ANMF'+(16+len(frame)).to_bytes(4, 'little')+bytes(16)+frame
    data = b'RIFF'+(len(frame)+4).to_bytes(4, 'little')+b'WEBP'+frame
    c, _ = community_api
    r = c.post('/api/community/posts', data={'metadata': json.dumps({'draft_id': str(uuid4()), 'kind': 'photo', 'title': '嵌套帧'})}, files={'photos': ('x.webp', data, 'image/webp')})
    assert r.status_code == 422
    assert c.get('/api/community/posts').json()['posts'] == []
