from contextlib import closing

from app.db import connect_db
from app.tests.test_community_api import publish
from app.tests.test_ootd_api import PHOTO
from app.tests.test_personal_api import A, B
from app.tests.test_personal_api import me_api as _me_api
from app.tests.test_personal_content import write

me_api=_me_api


def test_private_avatar_replacement_and_nickname_old_new_posts(me_api):
    c,path=me_api
    r=c.patch('/api/me/settings',json={'ticket':write(c,'settings'),'nickname':'我的衣橱'});assert r.status_code==200,r.text
    post=publish(c).json();assert post['author']['nickname']=='我的衣橱'
    assert c.patch('/api/me/settings',json={'ticket':write(c,'settings'),'nickname':'改名'}).status_code==200
    assert c.get('/api/community/posts/'+post['id'],headers={'X-Device-ID':B}).json()['author']['nickname']=='改名'
    token=write(c,'avatar')
    r=c.put('/api/me/avatar',data={'ticket':token},files={'photo':('avatar.jpg',PHOTO,'image/jpeg')});assert r.status_code==200,r.text
    assert r.json()['has_avatar']
    assert c.get('/api/me/avatar').content==PHOTO
    assert c.get('/api/me/avatar',headers={'X-Device-ID':B}).status_code==404
    assert c.request('DELETE','/api/me/avatar',json={'ticket':write(c,'avatar')}).status_code==200
    assert c.get('/api/me/avatar').status_code==404
    with closing(connect_db(path)) as db:
        assert db.execute('select nickname from personal_settings where owner_id=?',(A,)).fetchone()[0]=='改名'
    assert c.patch('/api/me/settings',json={'ticket':write(c,'settings'),'nickname':'   '}).status_code==400
