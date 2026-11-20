import json

from app.tests.test_community_api import publish
from app.tests.test_personal_api import A, B
from app.tests.test_personal_api import me_api as _me_api

me_api=_me_api


def test_real_received_actions_self_exclusion_and_private_vote_aggregation(me_api):
    c,_=me_api
    p=publish(c,kind='buy').json();pid=p['id'];uid=p['author']['id']
    c.put('/api/community/posts/'+pid+'/like')
    assert c.get('/api/me').json()['interactions']==0
    c.put('/api/community/posts/'+pid+'/like',headers={'X-Device-ID':B})
    c.put('/api/community/authors/'+uid+'/follow',headers={'X-Device-ID':B})
    c.post('/api/community/posts/'+pid+'/comments',headers={'X-Device-ID':B},json={'client_id':'11111111-1111-4111-8111-111111111111','text':'很好看'})
    c.put('/api/community/posts/'+pid+'/vote',headers={'X-Device-ID':B},json={'option_id':p['options'][0]['id']})
    overview=c.get('/api/me');assert overview.status_code==200,overview.text
    assert overview.json()['followers']==1 and overview.json()['interactions']==3
    items=c.get('/api/me/interactions').json()['items']
    assert {x['type'] for x in items}=={'like','comment','follow','vote'}
    vote=next(x for x in items if x['type']=='vote');assert vote['actor'] is None
    assert p['options'][0]['id'] not in json.dumps(vote)
    assert A not in json.dumps(items) and B not in json.dumps(items)
    assert len(c.get('/api/me/people?tab=followers').json()['items'])==1
    assert c.get('/api/me/people?tab=following',headers={'X-Device-ID':B}).json()['items'][0]['id']==uid
    assert len(c.get('/api/me/authors/'+uid+'/posts').json()['items'])==1
    c.delete('/api/community/posts/'+pid+'/like',headers={'X-Device-ID':B})
    assert 'like' not in {x['type'] for x in c.get('/api/me/interactions').json()['items']}
