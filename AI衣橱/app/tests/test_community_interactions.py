from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from app.db import connect_db
from app.tests.test_community_api import B, publish
from app.tests.test_community_api import community_api as _community_api

community_api = _community_api


def test_follow_like_comment_real_counts_and_privacy(community_api):
    c, path = community_api
    post = publish(c).json()
    headers = {'X-Device-ID': B}
    follow = '/api/community/authors/'+post['author']['id']+'/follow'
    assert c.put(follow).status_code == 400
    for _ in range(2):
        assert c.put(follow, headers=headers).json()['following'] is True
        assert c.put('/api/community/posts/'+post['id']+'/like', headers=headers).json()['likes'] == 1
    assert c.get('/api/community/posts?tab=following', headers=headers).json()['posts'][0]['id'] == post['id']
    comment_path = '/api/community/posts/'+post['id']+'/comments'
    body = {'client_id': str(uuid4()), 'text': '这套颜色很好看'}
    comment = c.post(comment_path, headers=headers, json=body)
    assert comment.status_code == 201
    assert c.post(comment_path, headers=headers, json=body).json()['id'] == comment.json()['id']
    assert c.post(comment_path, headers=headers, json=body | {'text': '改了内容'}).status_code == 409
    assert c.post(comment_path, headers=headers, json={'client_id': str(uuid4()), 'text': ' '}).status_code == 400
    view = c.get('/api/community/posts/'+post['id']).json()
    assert view['likes'] == view['comments'] == 1
    assert c.delete('/api/community/comments/'+comment.json()['id']).status_code == 404
    assert c.delete('/api/community/comments/'+comment.json()['id'], headers=headers).status_code == 204
    assert c.delete(follow, headers=headers).json()['following'] is False
    assert c.get('/api/community/posts?tab=following', headers=headers).json()['posts'] == []
    for _ in range(2):
        assert c.delete('/api/community/posts/'+post['id']+'/like', headers=headers).json()['likes'] == 0
    with connect_db(path) as db:
        assert db.execute('select count(*) from community_comments').fetchone()[0] == 0


def test_vote_unique_idempotent_option_belongs_to_post_and_concurrent(community_api):
    c, path = community_api
    post = publish(c, kind='buy').json()
    other = publish(c, kind='buy').json()
    route = '/api/community/posts/'+post['id']+'/vote'
    headers = {'X-Device-ID': B}
    assert c.put(route, headers=headers, json={'option_id': other['options'][0]['id']}).status_code == 404
    body = {'option_id': post['options'][0]['id']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: c.put(route, headers=headers, json=body), range(2)))
    assert all(r.status_code == 200 for r in results)
    assert c.put(route, headers=headers, json={'option_id': post['options'][1]['id']}).status_code == 409
    view = c.get('/api/community/posts/'+post['id'], headers=headers).json()
    assert view['votes'] == 1 and view['options'][0]['votes'] == 1 and view['my_vote'] == body['option_id']
    with connect_db(path) as db:
        assert db.execute('select count(*) from community_votes').fetchone()[0] == 1


def test_clear_removes_own_interactions_but_keeps_other_post(community_api):
    c, path = community_api
    post = publish(c, kind='buy').json()
    headers = {'X-Device-ID': B}
    assert c.put('/api/community/posts/'+post['id']+'/like', headers=headers).status_code == 200
    assert c.put('/api/community/authors/'+post['author']['id']+'/follow', headers=headers).status_code == 200
    assert c.put('/api/community/posts/'+post['id']+'/vote', headers=headers, json={'option_id': post['options'][0]['id']}).status_code == 200
    assert c.post('/api/community/posts/'+post['id']+'/comments', headers=headers, json={'client_id': str(uuid4()), 'text': '喜欢'}).status_code == 201
    assert c.delete('/api/wardrobe/items', headers=headers).status_code == 200
    view = c.get('/api/community/posts/'+post['id']).json()
    assert view['likes'] == view['comments'] == view['votes'] == 0
    with connect_db(path) as db:
        assert not db.execute('pragma foreign_key_check').fetchall()
