"""私密每日穿搭，照片不自动发送模型或社区。"""
import hashlib
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from app.db import connect_db, owner_lock
from app.models import PersonalOotd
from app.services import personal
from app.services.community import _image


def _row(db,owner,oid):
    row=db.execute('SELECT * FROM personal_ootds WHERE id=? AND owner_id=?',(oid,owner)).fetchone()
    if not row:
        raise HTTPException(404,'这条穿搭记录不存在。')
    return row


def view(row):
    return {k:row[k] for k in ('id','worn_on','title','note','kind','set_id','created_at','updated_at')}|{'has_photo':bool(row['photo_path']),'source_deleted':row['kind']=='outfit' and row['set_id'] is None}


def get(path,owner,oid):
    with closing(connect_db(path)) as db:
        return view(_row(db,owner,oid))


def listing(path,owner,cursor=None,limit=20):
    before=personal.decode_cursor('ootds',cursor)
    with closing(connect_db(path)) as db:
        rows=db.execute("SELECT * FROM personal_ootds WHERE owner_id=?"+(" AND (worn_on||char(10)||id)<?" if before else '')+' ORDER BY worn_on DESC,id DESC LIMIT ?', (owner,*([before] if before else []),limit+1)).fetchall()
        return {'items':[view(x) for x in rows[:limit]],'next_cursor':personal.encode_cursor('ootds',rows[limit-1]['worn_on']+'\n'+rows[limit-1]['id']) if len(rows)>limit else None}


def create(path,owner,draft,data=None):
    image=None
    if draft.kind=='photo':
        if not data or len(data)>10*1024*1024:
            raise HTTPException(422,'请选择10MB以内的穿搭照片。')
        _,extension=_image(data)
    elif data:
        raise HTTPException(422,'选择搭配时无需上传照片。')
    with owner_lock(path,owner),closing(connect_db(path)) as db:
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                payload=draft.model_dump(exclude={'ticket'})|{'image_hash':hashlib.sha256(data).hexdigest() if data else None}
                attempt=personal.consume_ticket(db,path,owner,draft.ticket,'ootd',payload)
                old=db.execute('SELECT * FROM personal_ootds WHERE owner_id=? AND client_id=?',(owner,attempt['request_id'])).fetchone()
                if not attempt['fresh']:
                    if not old:
                        raise HTTPException(410,'这条穿搭记录已删除，请重新确认后创建。')
                    return view(old),True
                if draft.set_id and not db.execute('SELECT 1 FROM outfit_sets WHERE id=? AND owner_id=?',(draft.set_id,owner)).fetchone():
                    raise HTTPException(404,'原搭配不存在或不可使用。')
                oid='D'+uuid4().hex
                if data:
                    image=Path(path).parent/'uploads'/owner/'personal'/(oid+extension)
                    image.parent.mkdir(parents=True,exist_ok=True);image.write_bytes(data)
                now=personal.stamp()
                insert=PersonalOotd(id=oid,owner_id=owner,client_id=attempt['request_id'],request_hash=attempt['request_hash'],worn_on=draft.worn_on,title=draft.title.strip(),note=draft.note.strip(),kind=draft.kind,photo_path=str(image.relative_to(Path(path).parent)) if image else None,set_id=draft.set_id,created_at=now,updated_at=now)
                personal.insert(db,'personal_ootds',insert)
                result=view(_row(db,owner,oid))
        except Exception:
            if image:
                image.unlink(missing_ok=True)
            raise
    return result,False


def update(path,owner,oid,patch):
    with owner_lock(path,owner),closing(connect_db(path)) as db,db:
        _row(db,owner,oid)
        db.execute('UPDATE personal_ootds SET worn_on=?,title=?,note=?,updated_at=? WHERE id=? AND owner_id=?',(patch.worn_on,patch.title.strip(),patch.note.strip(),personal.stamp(),oid,owner))
        return view(_row(db,owner,oid))


def photo(path,owner,oid):
    with closing(connect_db(path)) as db:
        row=_row(db,owner,oid)
        if not row['photo_path']:
            raise HTTPException(404,'此记录没有独立照片。')
        data=personal.private_file(path,owner,row['photo_path']).read_bytes()
        mime,_=_image(data)
        return data,mime


def delete(path,owner,oid):
    with owner_lock(path,owner),closing(connect_db(path)) as db:
        image=None;staged=None
        try:
            with db:
                db.execute('BEGIN IMMEDIATE');row=_row(db,owner,oid)
                if row['photo_path']:
                    image=personal.private_file(path,owner,row['photo_path']);staged=image.with_name(image.name+'.deleting');image.rename(staged)
                db.execute('DELETE FROM personal_ootds WHERE id=? AND owner_id=?',(oid,owner))
        except Exception:
            if staged and staged.exists():
                staged.rename(image)
            raise
        if staged:
            staged.unlink(missing_ok=True)
