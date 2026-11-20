"""设备个人中心；匿名写凭据不保留图片、文本或原始设备ID。"""
import base64
import hashlib
import hmac
import json
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from app.db import _quota_day, connect_db, owner_lock, quota_key, to_db_values
from app.models import PersonalWriteReceipt, PointDailyClaim, PointEntry


def insert(db, table, model):
    values=to_db_values(model)
    db.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join(':'+x for x in values)})",values)


def stamp():
    return datetime.now(UTC).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def _balance(db, owner):
    return db.execute('SELECT coalesce(sum(delta),0) FROM point_entries WHERE owner_id=?',(owner,)).fetchone()[0]


def check_in(path, owner, *, now=None):
    with owner_lock(path,owner),closing(connect_db(path)) as db,db:
        db.execute('BEGIN IMMEDIATE')
        current,day,end=_quota_day(now)
        db.execute('DELETE FROM point_daily_claims WHERE day<?',(day,))
        key=quota_key(path,owner)
        exists=db.execute('SELECT 1 FROM point_daily_claims WHERE owner_hash=? AND day=?',(key,day)).fetchone()
        if not exists:
            insert(db,'point_daily_claims',PointDailyClaim(owner_hash=key,day=day,expires_at=end.isoformat()))
            insert(db,'point_entries',PointEntry(id='E'+uuid4().hex,owner_id=owner,day=day,created_at=current.isoformat()))
        return {'awarded':not bool(exists),'day':day,'balance':_balance(db,owner)}


def encode_cursor(scope, value):
    return base64.urlsafe_b64encode(json.dumps([scope,value]).encode()).decode()


def decode_cursor(scope, cursor):
    if not cursor:
        return None
    try:
        obj=json.loads(base64.b64decode(cursor,altchars=b'-_',validate=True))
        if not isinstance(obj,list) or len(obj)!=2 or obj[0]!=scope or not isinstance(obj[1],str) or len(obj[1])>200:
            raise ValueError()
        return obj[1]
    except (ValueError,TypeError,UnicodeError):
        raise HTTPException(400,'列表位置无效，请刷新重试。') from None


def points(path,owner,cursor=None,limit=20):
    before=decode_cursor('points',cursor)
    with closing(connect_db(path)) as db:
        db.execute('BEGIN')
        rows=db.execute('SELECT day,delta,reason,created_at,id FROM point_entries WHERE owner_id=?'+(' AND day<?' if before else '')+' ORDER BY day DESC LIMIT ?', (owner,*([before] if before else []),limit+1)).fetchall()
        return {'balance':_balance(db,owner),'items':[dict(x) for x in rows[:limit]],'next_cursor':encode_cursor('points',rows[limit-1]['day']) if len(rows)>limit else None}


def issue_ticket(path,owner,purpose):
    if purpose not in {'ootd','feedback','avatar','settings','favorite'}:
        raise HTTPException(400,'操作类型无效。')
    with owner_lock(path,owner),closing(connect_db(path)) as db,db:
        db.execute('BEGIN IMMEDIATE')
        current,day,end=_quota_day()
        body={'owner':quota_key(path,owner),'purpose':purpose,'request':uuid4().hex,'expires':min(current.timestamp()+900,end.timestamp())}
        payload=base64.urlsafe_b64encode(json.dumps(body,sort_keys=True).encode()).decode()
        secret=(Path(path).parent/'.quota_salt').read_bytes()
        token=payload+'.'+hmac.new(secret,('personal:'+payload).encode(),hashlib.sha256).hexdigest()
        insert(db,'personal_write_receipts',PersonalWriteReceipt(token_hash=digest(token),owner_hash=body['owner'],purpose=purpose,day=day,expires_at=body['expires']))
        return {'ticket':token,'request_id':body['request'],'expires_at':body['expires']}


def consume_ticket(db,path,owner,ticket,purpose,payload):
    try:
        data,signature=ticket.split('.')
        secret=(Path(path).parent/'.quota_salt').read_bytes()
        if not hmac.compare_digest(signature,hmac.new(secret,('personal:'+data).encode(),hashlib.sha256).hexdigest()):
            raise ValueError()
        obj=json.loads(base64.urlsafe_b64decode(data))
        row=db.execute('SELECT * FROM personal_write_receipts WHERE token_hash=?',(digest(ticket),)).fetchone()
        current,_,_=_quota_day()
        if obj['owner']!=quota_key(path,owner) or obj['purpose']!=purpose or obj['expires']<=current.timestamp() or not row or row['state']=='revoked':
            raise ValueError()
    except (ValueError,KeyError,TypeError,OSError):
        raise HTTPException(410,'操作已失效或数据已清空，请确认后重新提交；当前输入仍保留。') from None
    hashed=digest(payload)
    if row['payload_hash'] and row['payload_hash']!=hashed:
        raise HTTPException(409,'本次提交内容已变化，请确认后开始新的提交。')
    fresh=row['state']=='issued'
    if fresh:
        db.execute("UPDATE personal_write_receipts SET state='consumed',payload_hash=? WHERE token_hash=?",(hashed,digest(ticket)))
    return {'fresh':fresh,'request_id':obj['request'],'request_hash':hashed}


def private_file(path,owner,relative):
    root=(Path(path).parent/'uploads'/owner).resolve()
    target=(Path(path).parent/relative).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(404,'照片不存在或暂不可用。')
    return target


def clear_records(db,path,owner):
    for table in ('personal_ootds','personal_favorites','personal_feedback','point_entries','personal_settings'):
        db.execute(f'DELETE FROM {table} WHERE owner_id=?',(owner,))
    db.execute("UPDATE personal_write_receipts SET state='revoked' WHERE owner_hash=? AND purpose<>'clear'",(quota_key(path,owner),))


def _clear_dir(path,operation):
    if not operation.startswith('K') or len(operation)!=33 or any(x not in '0123456789abcdef' for x in operation[1:]):
        raise HTTPException(500,'清理操作无效，请重试。')
    return Path(path).parent/'uploads'/'personal_trash'/operation


def prepare_clear(path,owner):
    from app.services import community
    operation='K'+uuid4().hex
    directory=_clear_dir(path,operation);directory.mkdir(parents=True)
    uploads=(Path(path).parent/'uploads').resolve()
    paths=[]
    private=uploads/owner
    if private.is_dir():
        paths.append(str(private.relative_to(uploads)))
    with closing(connect_db(path)) as db,db:
        me=community._author(db,owner)
        if me:
            for row in db.execute('SELECT id FROM community_posts WHERE author_id=?',(me['id'],)):
                public=community._public_directory(path,me['id'],row['id'])
                if public.is_dir():
                    paths.append(str(public.relative_to(uploads)))
        for row in db.execute('SELECT image_path FROM wardrobe_items WHERE owner_id=? AND image_path IS NOT NULL',(owner,)):
            file=(Path(path).parent/row[0]).resolve()
            if not file.is_relative_to(uploads):
                raise HTTPException(500,'照片清理未完成，请检查目录。')
            if file.is_file() and not file.is_relative_to(private) and str(file.relative_to(uploads)) not in paths:
                if db.execute('SELECT 1 FROM wardrobe_items WHERE owner_id<>? AND image_path=?',(owner,row[0])).fetchone():
                    raise HTTPException(500,'照片归属异常，未清空数据。')
                paths.append(str(file.relative_to(uploads)))
        # Manifest is durable before any rename; receipt decides restore vs purge.
        (directory/'manifest.json').write_text(json.dumps({'owner':owner,'paths':paths}))
        _,day,end=_quota_day()
        insert(db,'personal_write_receipts',PersonalWriteReceipt(token_hash=operation,owner_hash=quota_key(path,owner),purpose='clear',day=day,expires_at=end.timestamp()))
    return operation


def stage_private(path,owner,operation):
    directory=_clear_dir(path,operation)
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['owner']!=owner:
        raise HTTPException(500,'清理目录归属异常。')
    root=(Path(path).parent/'uploads').resolve()
    for index,relative in enumerate(manifest['paths']):
        original=(root/relative).resolve()
        if not original.is_relative_to(root) or original.is_relative_to(directory.resolve()):
            raise HTTPException(500,'清理路径异常。')
        target=directory/str(index)
        if original.exists():
            original.rename(target)


def finish_clear(path,operation,committed):
    import shutil
    directory=_clear_dir(path,operation)
    if directory.exists():
        manifest_file=directory/'manifest.json'
        if manifest_file.exists() and not committed:
            manifest=json.loads(manifest_file.read_text());root=(Path(path).parent/'uploads').resolve()
            for index,relative in reversed(list(enumerate(manifest['paths']))):
                original=(root/relative).resolve();target=directory/str(index)
                if not original.is_relative_to(root):
                    raise HTTPException(500,'恢复路径异常。')
                if target.exists():
                    if original.exists():
                        raise HTTPException(500,'恢复目录冲突，请联系维护者。')
                    original.parent.mkdir(parents=True,exist_ok=True);target.rename(original)
        shutil.rmtree(directory)
    with closing(connect_db(path)) as db,db:
        db.execute("DELETE FROM personal_write_receipts WHERE token_hash=? AND purpose='clear'",(operation,))


def recover_pending_clear(path,owner=None):
    with closing(connect_db(path)) as db:
        rows=db.execute("SELECT token_hash FROM personal_write_receipts WHERE purpose='clear'"+(' AND owner_hash=?' if owner else ''),([quota_key(path,owner)] if owner else [])).fetchall()
    for row in rows:
        operation=row[0];manifest=_clear_dir(path,operation)/'manifest.json'
        if not manifest.exists():
            finish_clear(path,operation,False);continue
        stored=json.loads(manifest.read_text())['owner']
        with owner_lock(path,stored),closing(connect_db(path)) as db:
            receipt=db.execute("SELECT * FROM personal_write_receipts WHERE token_hash=? AND owner_hash=?",(operation,quota_key(path,stored))).fetchone()
            if receipt:
                finish_clear(path,operation,receipt['state']=='consumed')


def _identity(db,path,owner):
    row=db.execute('SELECT * FROM personal_settings WHERE owner_id=?',(owner,)).fetchone()
    author=db.execute('SELECT id,nickname FROM community_authors WHERE owner_id=?',(owner,)).fetchone()
    return {'nickname':row['nickname'] if row else author['nickname'] if author else '衣友'+quota_key(path,owner)[-6:],
            'has_avatar':bool(row and row['avatar_path']),'avatar_version':row['avatar_version'] if row else ''}


def _ensure_settings(db,path,owner):
    from app.models import PersonalSettings
    if not db.execute('SELECT 1 FROM personal_settings WHERE owner_id=?',(owner,)).fetchone():
        insert(db,'personal_settings',PersonalSettings(owner_id=owner,nickname=_identity(db,path,owner)['nickname'],created_at=stamp()))


def _my_author(db,owner):
    row=db.execute('SELECT id FROM community_authors WHERE owner_id=?',(owner,)).fetchone()
    return row['id'] if row else None


def _received(db,owner):
    uid=_my_author(db,owner)
    if not uid:
        return []
    rows=[]
    for table,kind,text in [('community_likes','like','赞了你的穿搭'),('community_comments','comment','评论了你的穿搭')]:
        for r in db.execute(f'SELECT x.*,p.title,p.id AS post_id,a.nickname FROM {table} x JOIN community_posts p ON p.id=x.post_id JOIN community_authors a ON a.id=x.author_id WHERE p.author_id=? AND x.author_id<>? ORDER BY x.created_at DESC',(uid,uid)):
            rows.append({'id':kind+':'+(r['id'] if kind=='comment' else r['post_id']+r['author_id']),'type':kind,'created_at':r['created_at'],'text':r['text'] if kind=='comment' else text,'title':r['title'],'post_id':r['post_id'],'actor':{'id':r['author_id'],'nickname':r['nickname']}})
    for r in db.execute('SELECT p.id,p.title,count(*) AS count,max(v.created_at) AS created_at FROM community_votes v JOIN community_posts p ON p.id=v.post_id WHERE p.author_id=? AND v.author_id<>? GROUP BY p.id',(uid,uid)):
        rows.append({'id':'vote:'+r['id'],'type':'vote','created_at':r['created_at'],'text':f"当前收到{r['count']}票",'count':r['count'],'title':r['title'],'post_id':r['id'],'actor':None})
    for r in db.execute('SELECT f.created_at,a.id,a.nickname FROM community_follows f JOIN community_authors a ON a.id=f.follower_id WHERE f.followee_id=?',(uid,)):
        rows.append({'id':'follow:'+r['id'],'type':'follow','created_at':r['created_at'],'text':'关注了你','title':'','post_id':None,'actor':{'id':r['id'],'nickname':r['nickname']}})
    return rows


def overview(path,owner):
    with closing(connect_db(path)) as db:
        db.execute('BEGIN');uid=_my_author(db,owner)
        actions=_received(db,owner)
        return _identity(db,path,owner)|{'balance':_balance(db,owner),'following':db.execute('SELECT count(*) FROM community_follows WHERE follower_id=?',(uid,)).fetchone()[0],'followers':db.execute('SELECT count(*) FROM community_follows WHERE followee_id=?',(uid,)).fetchone()[0],'interactions':sum(x.get('count',1) for x in actions if x['type']!='follow')}


def _page(values,scope,cursor,limit,key=lambda x:x['created_at']+'\n'+x['id']):
    before=decode_cursor(scope,cursor)
    values=sorted(values,key=key,reverse=True)
    if before:
        values=[x for x in values if key(x)<before]
    return {'items':values[:limit],'next_cursor':encode_cursor(scope,key(values[limit-1])) if len(values)>limit else None}


def interactions(path,owner,cursor=None,limit=20):
    with closing(connect_db(path)) as db:
        db.execute('BEGIN')
        return _page(_received(db,owner),'interactions',cursor,limit)


def _post_item(db,row,uid):
    from app.services.community import _view
    p=_view(db,row,uid).model_dump(mode='json')
    return {'type':'post','id':p['id'],'created_at':p['created_at'],'title':p['title'],'post':p}


def outfit_view(db,owner,oid):
    from app.models import WardrobeItem
    row=db.execute('SELECT o.*,s.temp_c,s.occasion FROM outfit_sets o JOIN sessions s ON s.id=o.session_id AND s.owner_id=o.owner_id WHERE o.id=? AND o.owner_id=?',(oid,owner)).fetchone()
    if not row:
        raise HTTPException(404,'这套搭配不存在。')
    items=[];slots={}
    for item in db.execute('SELECT w.*,oi.slot FROM outfit_items oi JOIN wardrobe_items w ON w.id=oi.item_id AND w.owner_id=oi.owner_id WHERE oi.set_id=? AND oi.owner_id=?',(oid,owner)):
        value=dict(item);slot=value.pop('slot')
        for field in ('colors','seasons','sources'):
            value[field]=json.loads(value[field])
        items.append(WardrobeItem.model_validate(value).model_dump(mode='json'));slots[slot]=value['id']
    return {'type':'outfit','id':oid,'title':f"{row['temp_c']}℃ · {row['occasion']}",'reason':row['reason'],'degraded':bool(row['degraded']),'temp_c':row['temp_c'],'occasion':row['occasion'],'created_at':None,'items':items,'slots':slots}


def content(path,owner,tab,cursor=None,limit=20,status='all'):
    with closing(connect_db(path)) as db:
        db.execute('BEGIN');uid=_my_author(db,owner)
        if tab in {'published','favorites'}:
            if tab=='published':
                rows=db.execute('SELECT * FROM community_posts WHERE author_id=?',(uid,)).fetchall()
            else:
                rows=db.execute('SELECT p.* FROM community_posts p JOIN personal_favorites f ON f.post_id=p.id WHERE f.owner_id=?',(owner,)).fetchall()
            return _page([_post_item(db,r,uid) for r in rows],tab,cursor,limit)
        if tab=='outfits':
            rows=db.execute('SELECT id FROM outfit_sets o WHERE owner_id=? AND EXISTS(SELECT 1 FROM outfit_items i WHERE i.set_id=o.id AND i.owner_id=o.owner_id)',(owner,)).fetchall()
            return _page([outfit_view(db,owner,r['id']) for r in rows],tab,cursor,limit,key=lambda x:x['id'])
        from app.services.tryon import _view
        values=[]
        for r in db.execute('SELECT j.*,p.title FROM tryon_jobs j JOIN experience_products p ON p.id=j.product_id WHERE j.owner_id=?',(owner,)):
            state=r['status'];group='completed' if state=='completed' else 'processing' if state in {'submitting','starting','in_queue','processing'} else 'failed'
            if status!='all' and status!=group:
                continue
            values.append(_view(dict(r)).model_dump()|{'type':'tryon','title':r['title'],'created_at':datetime.fromtimestamp(r['created_at'],UTC).isoformat()})
        return _page(values,tab+':'+status,cursor,limit)


def people(path,owner,tab,cursor=None,limit=20):
    with closing(connect_db(path)) as db:
        db.execute('BEGIN');uid=_my_author(db,owner)
        join='followee_id' if tab=='following' else 'follower_id';where='follower_id' if tab=='following' else 'followee_id'
        rows=[dict(r) for r in db.execute(f'SELECT a.id,a.nickname,f.created_at FROM community_follows f JOIN community_authors a ON a.id=f.{join} WHERE f.{where}=?',(uid,))]
        return _page(rows,'people:'+tab,cursor,limit)


def author_posts(path,owner,author,cursor=None,limit=20):
    with closing(connect_db(path)) as db:
        db.execute('BEGIN')
        if not db.execute('SELECT 1 FROM community_authors WHERE id=?',(author,)).fetchone():
            raise HTTPException(404,'这位作者不存在。')
        return _page([_post_item(db,r,_my_author(db,owner)) for r in db.execute('SELECT * FROM community_posts WHERE author_id=?',(author,))],'author:'+author,cursor,limit)


def favorite(path,owner,pid,ticket=None,enabled=None):
    with owner_lock(path,owner),closing(connect_db(path)) as db,db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM community_posts WHERE id=?',(pid,)).fetchone():
            raise HTTPException(404,'这篇帖子已不存在。')
        if enabled is not None:
            attempt=consume_ticket(db,path,owner,ticket,'favorite',{'post':pid,'enabled':enabled})
            if attempt['fresh']:
                if enabled:
                    from app.models import PersonalFavorite
                    if not db.execute('SELECT 1 FROM personal_favorites WHERE owner_id=? AND post_id=?',(owner,pid)).fetchone():
                        insert(db,'personal_favorites',PersonalFavorite(owner_id=owner,post_id=pid,created_at=stamp()))
                else:
                    db.execute('DELETE FROM personal_favorites WHERE owner_id=? AND post_id=?',(owner,pid))
        return {'saved':bool(db.execute('SELECT 1 FROM personal_favorites WHERE owner_id=? AND post_id=?',(owner,pid)).fetchone())}


def settings(path,owner,patch):
    nickname=patch.nickname.strip()
    if not nickname:
        raise HTTPException(400,'昵称不能为空。')
    with owner_lock(path,owner),closing(connect_db(path)) as db,db:
        db.execute('BEGIN IMMEDIATE')
        attempt=consume_ticket(db,path,owner,patch.ticket,'settings',{'nickname':nickname})
        if attempt['fresh']:
            _ensure_settings(db,path,owner)
            db.execute('UPDATE personal_settings SET nickname=?,sources=json_set(sources,\'$.nickname\',\'user\') WHERE owner_id=?',(nickname,owner))
            db.execute('UPDATE community_authors SET nickname=?,sources=json_set(sources,\'$.nickname\',\'user\') WHERE owner_id=?',(nickname,owner))
        return _identity(db,path,owner)


def avatar(path,owner,ticket,data=None,remove=False):
    from app.services.community import _image
    if not remove:
        if not data or len(data)>2*1024*1024:
            raise HTTPException(422,'请选择2MB以内的头像照片。')
        _,extension=_image(data)
    image=None;old=None
    with owner_lock(path,owner),closing(connect_db(path)) as db:
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                attempt=consume_ticket(db,path,owner,ticket,'avatar',{'remove':remove,'hash':hashlib.sha256(data).hexdigest() if data else None})
                if attempt['fresh']:
                    _ensure_settings(db,path,owner)
                    row=db.execute('SELECT avatar_path FROM personal_settings WHERE owner_id=?',(owner,)).fetchone()
                    if row['avatar_path']:
                        old=private_file(path,owner,row['avatar_path'])
                    version=uuid4().hex
                    if not remove:
                        image=Path(path).parent/'uploads'/owner/'personal'/('avatar-'+version+extension)
                        image.parent.mkdir(parents=True,exist_ok=True);image.write_bytes(data)
                    db.execute('UPDATE personal_settings SET avatar_path=?,avatar_version=? WHERE owner_id=?',(str(image.relative_to(Path(path).parent)) if image else None,version,owner))
                value=_identity(db,path,owner)
        except Exception:
            if image:
                image.unlink(missing_ok=True)
            raise
        if old:
            old.unlink(missing_ok=True)
    return value


def avatar_photo(path,owner):
    from app.services.community import _image
    with closing(connect_db(path)) as db:
        row=db.execute('SELECT avatar_path FROM personal_settings WHERE owner_id=?',(owner,)).fetchone()
        if not row or not row['avatar_path']:
            raise HTTPException(404,'还没有上传头像。')
        data=private_file(path,owner,row['avatar_path']).read_bytes();mime,_=_image(data)
        return data,mime


def feedback(path,owner,body):
    from app.models import PersonalFeedback
    text=body.text.strip()
    if not text:
        raise HTTPException(400,'请输入反馈内容。')
    with owner_lock(path,owner),closing(connect_db(path)) as db,db:
        db.execute('BEGIN IMMEDIATE')
        attempt=consume_ticket(db,path,owner,body.ticket,'feedback',{'category':body.category,'text':text})
        old=db.execute('SELECT id FROM personal_feedback WHERE owner_id=? AND client_id=?',(owner,attempt['request_id'])).fetchone()
        if not attempt['fresh']:
            if not old:
                raise HTTPException(410,'反馈记录已清空，请重新确认提交。')
            return {'id':old['id'],'message':'反馈已保存到测试服务'},True
        fid='F'+uuid4().hex
        insert(db,'personal_feedback',PersonalFeedback(id=fid,owner_id=owner,client_id=attempt['request_id'],request_hash=attempt['request_hash'],category=body.category,text=text,created_at=stamp()))
        return {'id':fid,'message':'反馈已保存到测试服务'},False


def historical_tryon(path,owner,task_id):
    from app.services.tryon import _view
    with closing(connect_db(path)) as db:
        row=db.execute('SELECT * FROM tryon_jobs WHERE id=? AND owner_id=?',(task_id,owner)).fetchone()
        if not row:
            raise HTTPException(404,'这条历史记录不存在或已删除。')
        return _view(dict(row))
