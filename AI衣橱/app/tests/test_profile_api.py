from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app.db import connect_db, init_db
from app.main import app
from app.routers.wardrobe import database_path

A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
B = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'


@pytest.fixture
def profile_api(tmp_path):
    path = tmp_path / 'app.db'
    init_db(path)
    init_db(path)
    app.dependency_overrides[database_path] = lambda: path
    try:
        with TestClient(app, headers={'X-Device-ID': A}) as client:
            yield client, path
    finally:
        app.dependency_overrides.pop(database_path, None)


def test_profile_save_read_isolated_and_cleared(profile_api):
    client, path = profile_api
    assert client.get('/api/profile').json()['height_cm'] is None
    values = {'height_cm': 165.5, 'weight_kg': 55.2, 'body_shape': 'A'}
    response = client.patch('/api/profile', json=values)
    assert response.status_code == 200
    for key, value in values.items():
        assert response.json()[key] == value
        assert response.json()['sources'][key] == 'user'
    assert client.get('/api/profile').json() == response.json()
    assert client.get('/api/profile', headers={'X-Device-ID': B}).json()['height_cm'] is None
    assert client.patch('/api/profile', json={'weight_kg': None}).json()['height_cm'] == 165.5
    client.patch('/api/profile', headers={'X-Device-ID': B}, json={'height_cm': 180})
    assert client.delete('/api/wardrobe/items').status_code == 200
    assert client.get('/api/profile').json()['height_cm'] is None
    with closing(connect_db(path)) as db:
        assert db.execute('SELECT count(*) FROM body_profiles WHERE owner_id=?', (A,)).fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM body_profiles WHERE owner_id=?', (B,)).fetchone()[0] == 1


@pytest.mark.parametrize('shape', ['X', 'A', 'TY', 'H', 'O'])
def test_profile_five_shapes(profile_api, shape):
    client, _ = profile_api
    assert client.patch('/api/profile', json={'body_shape': shape}).json()['body_shape'] == shape


@pytest.mark.parametrize('values', [{}, {'height_cm': 0}, {'weight_kg': -1}, {'height_cm': True},
                                   {'height_cm': '165'}, {'body_shape': 'unknown'}, {'owner_id': B}])
def test_profile_invalid_input(profile_api, values):
    client, _ = profile_api
    response = client.patch('/api/profile', json=values)
    assert response.status_code == 400
    assert 'detail' in response.json()
    assert 'Traceback' not in response.text


def test_profile_requires_device(profile_api):
    client, _ = profile_api
    assert client.get('/api/profile', headers={'X-Device-ID': ''}).status_code == 400
