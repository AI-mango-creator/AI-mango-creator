"""私有异步试穿。没有SDK、后台worker或生产mock分支。"""
import base64
import hashlib
import shutil
from contextlib import closing
from pathlib import Path
from time import time

from fastapi import HTTPException

from app.db import connect_db, issue_tryon_ticket, owner_lock, reserve_tryon
from app.llm import client
from app.llm.errors import LLMError
from app.models import ExperienceProductView, TryonView
from app.services.community import MAX_IMAGE, _image

MESSAGES = {
    'submitting': '正在提交，请勿重复操作。', 'starting': '试穿任务已提交，正在准备…',
    'in_queue': '试穿排队中…', 'processing': '试穿中…', 'completed': '试穿完成，仅供外观参考。',
    'failed': '试穿未成功，请检查照片后重新确认试穿。',
    'unknown': '提交结果尚未确认，可能已计费；不会自动重复提交，请稍后联系服务维护者核对。',
    'timed_out': '本次等待已结束，远端可能仍在处理；不会自动重新生成，请稍后核对。',
}


def _view(row):
    message = {'MODEL_CONFIG': '试穿服务暂不可用，请联系维护者检查配置。', 'MODEL_RATE_LIMIT': '试穿服务正忙，请稍后重新确认试穿。', 'parse': '试穿结果格式有误，请稍后重新确认试穿。'}.get(row['error_kind'], MESSAGES[row['status']]) if row['status']=='failed' else MESSAGES[row['status']]
    return TryonView(id=row['id'], product_id=row['product_id'], status=row['status'],
                     message=message, has_result=row['status']=='completed' and bool(row['result_path']), latency_ms=row['latency_ms'])


def products(path):
    with closing(connect_db(path)) as db:
        return [ExperienceProductView(**dict(r)) for r in db.execute('SELECT id,title,category,source_label FROM experience_products ORDER BY created_at DESC,id')]


def product(path, product_id):
    with closing(connect_db(path)) as db:
        row = db.execute('SELECT * FROM experience_products WHERE id=?', (product_id,)).fetchone()
        if row is None:
            raise HTTPException(404, '这件体验服饰不存在。')
        return dict(row)


def _read_image(path, relative, root):
    target = (Path(path).resolve().parent/relative).resolve()
    allowed = (Path(path).resolve().parent/'uploads'/root).resolve()
    if not target.is_relative_to(allowed) or not target.is_file() or target.stat().st_size > MAX_IMAGE:
        raise HTTPException(404, '照片不存在或暂不可用。')
    data = target.read_bytes()
    mime, _ = _image(data)
    return data, mime


def product_photo(path, product_id):
    item = product(path, product_id)
    return _read_image(path, item['image_path'], 'catalog/'+product_id)


def ticket(path, owner, product_id):
    product(path, product_id)
    return issue_tryon_ticket(path, owner, product_id)


def _job(db, owner, task_id):
    row = db.execute('SELECT * FROM tryon_jobs WHERE id=? AND owner_id=?', (task_id, owner)).fetchone()
    if row is None:
        raise HTTPException(404, '试穿任务不存在或已删除。')
    return dict(row)


def recent(path, owner, product_id):
    with closing(connect_db(path)) as db:
        return [_view(dict(r)) for r in db.execute('SELECT * FROM tryon_jobs WHERE owner_id=? AND product_id=? ORDER BY created_at DESC LIMIT 3', (owner, product_id))]


def create(path, owner, product_id, token, photo, consent):
    path = Path(path).resolve()
    if not consent:
        raise HTTPException(422, '请先确认照片使用权及向试穿服务发送处理。')
    _, extension = _image(photo)
    garment, _ = product_photo(path, product_id)
    item = product(path, product_id)
    try:
        client.tryon_configuration()
    except LLMError:
        raise HTTPException(503, '试穿服务暂未启用，请联系维护者或稍后再试。') from None
    digest = hashlib.sha256(product_id.encode()+photo).hexdigest()
    with owner_lock(path, owner):
        row, reused = reserve_tryon(path, owner, product_id, token, digest)
        if reused:
            return _view(row)
        relative = f'uploads/{owner}/tryon/{row["id"]}/person{extension}'
        try:
            image = path.parent/relative
            image.parent.mkdir(parents=True, exist_ok=False)
            image.write_bytes(photo)
            with closing(connect_db(path)) as db, db:
                db.execute('UPDATE tryon_jobs SET portrait_path=? WHERE id=? AND owner_id=?', (relative, row['id'], owner))
        except OSError:
            with closing(connect_db(path)) as db, db:
                db.execute("UPDATE tryon_jobs SET status='failed',error_kind='storage' WHERE id=? AND owner_id=?", (row['id'], owner))
            raise HTTPException(503, '试穿照片暂时无法保存，请稍后再试。') from None
    state, provider, error = 'starting', None, None
    try:
        with client.request_context(case_id=row['id'], prompt_version='fashn.tryon-v1.6'):
            response = client.tryon_submit(photo, garment, item['category'])
        if response.error:
            state, error = 'failed', 'provider'
        else:
            provider = response.id
    except LLMError as exc:
        error = exc.code
        state = 'failed' if exc.http_status in (401, 403, 429) else 'unknown'
    with owner_lock(path, owner), closing(connect_db(path)) as db, db:
        _job(db, owner, row['id'])  # clear/delete won: never recreate anything.
        db.execute('UPDATE tryon_jobs SET status=?,provider_task_id=?,error_kind=? WHERE id=? AND owner_id=?', (state, provider, error, row['id'], owner))
        return _view(_job(db, owner, row['id']))


def get(path, owner, task_id):
    path = Path(path).resolve()
    with owner_lock(path, owner), closing(connect_db(path)) as db, db:
        row = _job(db, owner, task_id)
        now = time()
        if row['status'] == 'submitting' and now-row['created_at'] >= 25:
            db.execute("UPDATE tryon_jobs SET status='unknown' WHERE id=? AND owner_id=?", (task_id, owner))
            return _view(_job(db, owner, task_id))
        if row['status'] not in ('starting', 'in_queue', 'processing'):
            return _view(row)
        if now-row['created_at'] >= 120 or row['polls'] >= 30:
            db.execute("UPDATE tryon_jobs SET status='timed_out',latency_ms=? WHERE id=? AND owner_id=?", (round((now-row['created_at'])*1000), task_id, owner))
            return _view(_job(db, owner, task_id))
        if now-row['last_poll'] < 2:
            return _view(row)
        lease = now+25
        db.execute('UPDATE tryon_jobs SET polls=polls+1,last_poll=? WHERE id=? AND owner_id=?', (lease, task_id, owner))
    image_data, extension, state, error = None, None, row['status'], None
    try:
        with client.request_context(case_id=task_id, prompt_version='fashn.tryon-v1.6'):
            response = client.tryon_status(row['provider_task_id'])
        if response.id != row['provider_task_id'] or response.status is None:
            raise LLMError('MODEL_RESPONSE', '任务响应无效。')
        state = response.status
        if response.error:
            state, error = 'failed', 'provider'
        elif state == 'completed':
            if not response.output or len(response.output) != 1:
                raise ValueError()
            head, encoded = response.output[0].split(',', 1)
            if head not in ('data:image/jpeg;base64', 'data:image/png;base64', 'data:image/webp;base64') or len(encoded) > 14*1024*1024:
                raise ValueError()
            image_data = base64.b64decode(encoded, validate=True)
            mime, extension = _image(image_data)
            if head != f'data:{mime};base64':
                raise ValueError()
    except LLMError as exc:
        error = exc.code
        if exc.code in ('MODEL_CONFIG', 'MODEL_RATE_LIMIT', 'MODEL_RESPONSE'):
            state = 'failed'
    except (ValueError, HTTPException):
        state, error = 'failed', 'parse'
    with owner_lock(path, owner), closing(connect_db(path)) as db, db:
        current = _job(db, owner, task_id)
        if current['last_poll'] != lease or current['status'] in ('completed', 'failed', 'timed_out'):
            return _view(current)
        result = None
        if image_data is not None and state == 'completed':
            result = f'uploads/{owner}/tryon/{task_id}/result{extension}'
            target = path.parent/result
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(image_data)
        db.execute('UPDATE tryon_jobs SET status=?,result_path=?,error_kind=?,last_poll=?,latency_ms=? WHERE id=? AND owner_id=?',
                   (state, result, error, time(), round((time()-row['created_at'])*1000), task_id, owner))
        return _view(_job(db, owner, task_id))


def result_photo(path, owner, task_id):
    with closing(connect_db(path)) as db:
        row = _job(db, owner, task_id)
        if row['status'] != 'completed' or not row['result_path']:
            raise HTTPException(404, '试穿结果暂不可用。')
        return _read_image(path, row['result_path'], owner+'/tryon/'+task_id)


def delete(path, owner, task_id):
    with owner_lock(path, owner), closing(connect_db(path)) as db, db:
        _job(db, owner, task_id)
        directory = Path(path).resolve().parent/'uploads'/owner/'tryon'/task_id
        if directory.is_dir():
            shutil.rmtree(directory)
        db.execute('DELETE FROM tryon_jobs WHERE id=? AND owner_id=?', (task_id, owner))


def clear_for_owner(db, owner):
    db.execute('DELETE FROM tryon_jobs WHERE owner_id=?', (owner,))
