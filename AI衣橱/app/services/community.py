"""应用内社区：只公开显式发布的副本；私人衣柜查询始终带owner。"""
import base64
import hashlib
import json
import re
import shutil
import zlib
from contextlib import closing
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from app.db import connect_db, owner_lock, to_db_values
from app.models import (
    CommunityAuthor,
    CommunityAuthorView,
    CommunityFeed,
    CommunityMedia,
    CommunityMediaView,
    CommunityOption,
    CommunityOptionView,
    CommunityPost,
    CommunityPostView,
)

MAX_IMAGE = 10 * 1024 * 1024
MAX_TOTAL = 30 * 1024 * 1024


def _insert(db, table, record):
    values = to_db_values(record)
    db.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join(':'+x for x in values)})", values)


def _author(db, owner, create=False):
    row = db.execute('SELECT * FROM community_authors WHERE owner_id=?', (owner,)).fetchone()
    if row is None and create:
        uid = 'U' + uuid4().hex
        _insert(db, 'community_authors', CommunityAuthor(id=uid, owner_id=owner, nickname='衣友'+uid[-6:]))
        row = db.execute('SELECT * FROM community_authors WHERE id=?', (uid,)).fetchone()
    return row


def _post(db, post_id):
    row = db.execute('SELECT * FROM community_posts WHERE id=?', (post_id,)).fetchone()
    if row is None:
        raise HTTPException(404, '这篇帖子已不存在。')
    return row


def _count(db, table, post_id):
    return db.execute(f'SELECT count(*) FROM {table} WHERE post_id=?', (post_id,)).fetchone()[0]


def _view(db, row, viewer):
    author = db.execute('SELECT id,nickname FROM community_authors WHERE id=?', (row['author_id'],)).fetchone()
    media = [CommunityMediaView(id=x['id'], caption=x['caption']) for x in db.execute(
        'SELECT id,caption FROM community_media WHERE post_id=? ORDER BY position', (row['id'],))]
    options = [CommunityOptionView(id=x['id'], label=x['label'], media_id=x['media_id'],
                votes=db.execute('SELECT count(*) FROM community_votes WHERE option_id=?', (x['id'],)).fetchone()[0])
               for x in db.execute('SELECT * FROM community_poll_options WHERE post_id=? ORDER BY position', (row['id'],))]
    vote = db.execute('SELECT option_id FROM community_votes WHERE post_id=? AND author_id=?', (row['id'], viewer)).fetchone()
    return CommunityPostView(id=row['id'], author=CommunityAuthorView(**dict(author)), kind=row['kind'],
        title=row['title'], body=row['body'], created_at=row['created_at'], media=media, options=options,
        likes=_count(db, 'community_likes', row['id']), comments=_count(db, 'community_comments', row['id']),
        votes=_count(db, 'community_votes', row['id']),
        liked=db.execute('SELECT 1 FROM community_likes WHERE post_id=? AND author_id=?', (row['id'], viewer)).fetchone() is not None,
        following=db.execute('SELECT 1 FROM community_follows WHERE follower_id=? AND followee_id=?', (viewer, row['author_id'])).fetchone() is not None,
        my_vote=vote['option_id'] if vote else None, can_delete=viewer == row['author_id'])


def _decode_cursor(value):
    if not value:
        return None
    try:
        values = json.loads(base64.b64decode(value, altchars=b'-_', validate=True))
        if not isinstance(values, list) or len(values) != 2 or not all(isinstance(x, str) for x in values):
            raise ValueError()
        datetime.fromisoformat(values[0])
        if len(values[1]) > 80:
            raise ValueError()
        return values
    except (ValueError, TypeError, UnicodeError):
        raise HTTPException(400, '列表位置无效，请刷新重试。') from None


def _encode_cursor(row):
    return base64.urlsafe_b64encode(json.dumps([row['created_at'], row['id']]).encode()).decode()


def list_posts(path, owner, tab='all', cursor=None, limit=20):
    position = _decode_cursor(cursor)
    with closing(connect_db(path)) as db:
        db.execute('BEGIN')
        viewer = _author(db, owner)
        uid = viewer['id'] if viewer else None
        clauses, args = [], []
        if tab == 'following':
            clauses.append('author_id IN (SELECT followee_id FROM community_follows WHERE follower_id=?)')
            args.append(uid)
        elif tab == 'outfits':
            clauses.append("kind='outfit'")
        elif tab == 'votes':
            clauses.append("kind IN ('poll','buy')")
        if position:
            clauses.append('(created_at,id)<(?,?)')
            args.extend(position)
        query = 'SELECT * FROM community_posts' + (' WHERE '+ ' AND '.join(clauses) if clauses else '')
        rows = db.execute(query+' ORDER BY created_at DESC,id DESC LIMIT ?', (*args, limit+1)).fetchall()
        return CommunityFeed(posts=[_view(db, row, uid) for row in rows[:limit]],
                             next_cursor=_encode_cursor(rows[limit-1]) if len(rows) > limit else None)


def get_post(path, owner, post_id):
    with closing(connect_db(path)) as db:
        db.execute('BEGIN')
        viewer = _author(db, owner)
        return _view(db, _post(db, post_id), viewer['id'] if viewer else None)



def _valid_jpeg(data):
    # 验证分段长度、图像尺寸、扫描和结束标记；不引入本地图片/模型依赖。
    pos, frame, scan = 2, False, False
    while pos < len(data):
        if data[pos] != 255:
            return False
        while pos < len(data) and data[pos] == 255:
            pos += 1
        if pos >= len(data):
            return False
        marker = data[pos]
        pos += 1
        if marker == 217:
            return frame and scan and pos == len(data)
        if marker in (0, 216) or pos+2 > len(data):
            return False
        length = int.from_bytes(data[pos:pos+2], 'big')
        end = pos+length
        if length < 2 or end > len(data):
            return False
        if marker in (192, 193, 194, 195, 197, 198, 199, 201, 202, 203, 205, 206, 207):
            if length < 8 or not int.from_bytes(data[pos+3:pos+5], 'big') or not int.from_bytes(data[pos+5:pos+7], 'big'):
                return False
            frame = True
        pos = end
        if marker == 218:
            if not frame or length < 6:
                return False
            scan = True
            start = pos
            while pos < len(data):
                found = data.find(b'\xff', pos)
                if found < 0 or found+1 >= len(data):
                    return False
                if data[found+1] == 0 or 208 <= data[found+1] <= 215:
                    pos = found+2
                    continue
                pos = found
                break
            if pos == start:
                return False
    return False


def _valid_png(data):
    pos, header, pixels = 8, False, False
    while pos+12 <= len(data):
        length = int.from_bytes(data[pos:pos+4], 'big')
        end = pos+12+length
        if end > len(data):
            return False
        kind = data[pos+4:pos+8]
        content = data[pos+8:pos+8+length]
        if zlib.crc32(kind+content) != int.from_bytes(data[end-4:end], 'big'):
            return False
        if not header:
            if kind != b'IHDR' or length != 13 or not int.from_bytes(content[:4], 'big') or not int.from_bytes(content[4:8], 'big'):
                return False
            header = True
        elif kind == b'IHDR':
            return False
        if kind == b'IDAT' and length:
            pixels = True
        if kind == b'IEND':
            return length == 0 and pixels and end == len(data)
        pos = end
    return False


def _valid_webp(data, *, frame=False):
    if len(data) < 20 or int.from_bytes(data[4:8], 'little')+8 != len(data):
        return False
    pos, pixels = 12, False
    while pos+8 <= len(data):
        kind, length = data[pos:pos+4], int.from_bytes(data[pos+4:pos+8], 'little')
        # A frame contains only image/alpha chunks, never another ANMF.
        # Bound recursion to one frame to avoid repeated attacker-controlled copies.
        if frame and kind not in (b'ALPH', b'VP8 ', b'VP8L'):
            return False
        end = pos+8+length
        if end > len(data):
            return False
        chunk = data[pos+8:end]
        if kind == b'VP8 ':
            pixels = length >= 10 and chunk[3:6] == b'\x9d\x01\x2a' and int.from_bytes(chunk[6:8], 'little') & 16383 > 0 and int.from_bytes(chunk[8:10], 'little') & 16383 > 0
        elif kind == b'VP8L':
            pixels = length >= 5 and chunk[0] == 47
        elif kind == b'ANMF' and length > 16:
            content = chunk[16:]
            if not _valid_webp(b'RIFF'+(len(content)+4).to_bytes(4, 'little')+b'WEBP'+content, frame=True):
                return False
            pixels = True
        pos = end+(length % 2)
    return bool(pixels and pos == len(data))


def _image(data):
    if not data or len(data) > MAX_IMAGE:
        raise HTTPException(413 if data else 422, '请选择不超过10MB的有效照片。')
    if data.startswith(b'\xff\xd8\xff') and _valid_jpeg(data):
        return 'image/jpeg', '.jpg'
    if data.startswith(b'\x89PNG\r\n\x1a\n') and _valid_png(data):
        return 'image/png', '.png'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP' and _valid_webp(data):
        return 'image/webp', '.webp'
    raise HTTPException(422, '社区仅支持JPG、PNG或WebP图片，请重新选择。')


def _public_directory(path, author_id, post_id):
    base = (Path(path).parent/'uploads').resolve()/'community'
    directory = base/author_id/post_id
    if directory.resolve() != directory:
        raise HTTPException(404, '帖子照片不存在。')
    return directory


def publish(path, owner, draft, photos):
    path = Path(path).resolve()
    if sum(len(x) for x in photos) > MAX_TOTAL:
        raise HTTPException(413, '本帖图片总大小不能超过30MB。')
    expected = {'photo': range(1, 10), 'buy': range(1, 2), 'poll': range(len(draft.options), len(draft.options)+1), 'outfit': range(1)}
    if len(photos) not in expected[draft.kind]:
        raise HTTPException(422, '请按发布类型选择正确数量的照片。')
    for data in photos:
        _image(data)
    canonical = draft.model_dump(mode='json')
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()
                            + b''.join(hashlib.sha256(x).digest() for x in photos)).hexdigest()
    directory = None
    with owner_lock(path, owner), closing(connect_db(path)) as db:
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                author = _author(db, owner, True)
                old = db.execute('SELECT * FROM community_posts WHERE author_id=? AND draft_id=?', (author['id'], str(draft.draft_id))).fetchone()
                if old:
                    if old['request_hash'] != digest:
                        raise HTTPException(409, '同一草稿的内容已经变化，请新建草稿后发布。')
                    return _view(db, old, author['id']), True
                images = [(data, '') for data in photos]
                if draft.kind == 'outfit':
                    images = []
                    for item_id in draft.item_ids:
                        item = db.execute('SELECT image_path,category,sub,colors FROM wardrobe_items WHERE id=? AND owner_id=?', (item_id, owner)).fetchone()
                        if item is None:
                            raise HTTPException(404, '只能选择自己衣橱里的单品。')
                        if not item['image_path']:
                            raise HTTPException(422, '请只选择有照片的衣物。')
                        source = (Path(path).parent/item['image_path']).resolve()
                        if not source.is_relative_to((Path(path).parent/'uploads').resolve()/owner) or not source.is_file():
                            raise HTTPException(404, '所选衣物照片无法读取。')
                        data = source.read_bytes()
                        _image(data)
                        caption = ' · '.join(filter(None, [item['sub'], ' / '.join(json.loads(item['colors']))]))
                        images.append((data, caption))
                    if sum(len(x[0]) for x in images) > MAX_TOTAL:
                        raise HTTPException(413, '所选衣物照片总大小超过30MB，请减少单品。')
                post_id = 'P'+uuid4().hex
                directory = _public_directory(path, author['id'], post_id)
                directory.mkdir(parents=True)
                record = CommunityPost(id=post_id, author_id=author['id'], kind=draft.kind,
                    title=draft.title, body=draft.body, draft_id=str(draft.draft_id), request_hash=digest)
                _insert(db, 'community_posts', record)
                media_ids = []
                for index, (data, caption) in enumerate(images):
                    mime, extension = _image(data)
                    media_id = 'M'+uuid4().hex
                    image = directory/(media_id+extension)
                    image.write_bytes(data)
                    _insert(db, 'community_media', CommunityMedia(id=media_id, post_id=post_id, position=index,
                        file_path=str(image.relative_to(Path(path).parent)), mime_type=mime, caption=caption))
                    media_ids.append(media_id)
                labels = [x.label for x in draft.options] if draft.kind == 'poll' else ['不值得', '值得'] if draft.kind == 'buy' else []
                for index, label in enumerate(labels):
                    _insert(db, 'community_poll_options', CommunityOption(id='O'+uuid4().hex, post_id=post_id,
                        position=index, label=label, media_id=media_ids[index] if draft.kind == 'poll' else None,
                        sources={'label': 'derived' if draft.kind == 'buy' else 'user'}))
                result = _view(db, _post(db, post_id), author['id'])
            return result, False
        except Exception:
            if directory and directory.is_dir():
                shutil.rmtree(directory)
            raise


def photo_file(path, post_id, media_id):
    with closing(connect_db(path)) as db:
        post = _post(db, post_id)
        media = db.execute('SELECT * FROM community_media WHERE id=? AND post_id=?', (media_id, post_id)).fetchone()
        if media is None:
            raise HTTPException(404, '帖子照片不存在。')
        image = (Path(path).parent/media['file_path']).resolve()
        if not image.is_relative_to(_public_directory(path, post['author_id'], post_id)) or not image.is_file():
            raise HTTPException(404, '帖子照片不存在。')
        return image, media['mime_type']


def _trash(path, owner):
    base = (Path(path).parent/'uploads').resolve()/'community_trash'/owner
    if base.resolve() != base:
        raise HTTPException(500, '照片暂存目录异常，请稍后重试。')
    return base


def stage_owner_posts(db, path, owner, post_id=None):
    author = _author(db, owner)
    if not author:
        return []
    rows = db.execute('SELECT id FROM community_posts WHERE author_id=?'+(' AND id=?' if post_id else ''),
                      (author['id'], post_id) if post_id else (author['id'],)).fetchall()
    staged = []
    try:
        for row in rows:
            original = _public_directory(path, author['id'], row['id'])
            target = _trash(path, owner)/row['id']
            if original.is_dir():
                target.parent.mkdir(parents=True, exist_ok=True)
                original.rename(target)
                staged.append((original, target))
        return staged
    except OSError:
        restore_staged(staged)
        raise HTTPException(500, '照片撤回暂未完成，请稍后重试。') from None


def restore_staged(staged):
    for original, target in reversed(staged):
        if target.exists():
            target.rename(original)


def purge_trash(path, owner, post_id=None):
    target = _trash(path, owner)
    if post_id:
        if not re.fullmatch(r'P[0-9a-f]{32}', post_id):
            raise HTTPException(404, '这篇帖子已不存在。')
        target = target/post_id
    if not target.exists():
        return False
    if target.resolve() != target:
        raise HTTPException(500, '照片暂存目录异常，请稍后重试。')
    try:
        shutil.rmtree(target)
    except OSError:
        raise HTTPException(500, '帖子已撤回，照片清理未完成，请重试。') from None
    return True


def clear_for_owner(db, owner):
    db.execute('DELETE FROM community_authors WHERE owner_id=?', (owner,))


def delete_post(path, owner, post_id):
    staged = []
    with owner_lock(path, owner), closing(connect_db(path)) as db:
        row = db.execute('SELECT p.id FROM community_posts p JOIN community_authors a ON a.id=p.author_id WHERE p.id=? AND a.owner_id=?', (post_id, owner)).fetchone()
        if not row:
            if purge_trash(path, owner, post_id):
                return
            raise HTTPException(404, '这篇帖子不存在或不能由你删除。')
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                staged = stage_owner_posts(db, path, owner, post_id)
                db.execute('DELETE FROM community_posts WHERE id=?', (post_id,))
        except Exception:
            restore_staged(staged)
            raise
        purge_trash(path, owner, post_id)


def follow_author(path, owner, target, enabled):
    from app.models import CommunityFollow

    with owner_lock(path, owner), closing(connect_db(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM community_authors WHERE id=?', (target,)).fetchone():
            raise HTTPException(404, '这位作者已不存在。')
        me = _author(db, owner, enabled)
        if me and me['id'] == target:
            raise HTTPException(400, '不能关注自己。')
        if me:
            if enabled:
                if not db.execute('SELECT 1 FROM community_follows WHERE follower_id=? AND followee_id=?', (me['id'], target)).fetchone():
                    _insert(db, 'community_follows', CommunityFollow(follower_id=me['id'], followee_id=target))
            else:
                db.execute('DELETE FROM community_follows WHERE follower_id=? AND followee_id=?', (me['id'], target))
        return {'following': enabled}


def like_post(path, owner, post_id, enabled):
    from app.models import CommunityLike

    with owner_lock(path, owner), closing(connect_db(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        post = _post(db, post_id)
        me = _author(db, owner, enabled)
        if me:
            if enabled:
                if not db.execute('SELECT 1 FROM community_likes WHERE post_id=? AND author_id=?', (post_id, me['id'])).fetchone():
                    _insert(db, 'community_likes', CommunityLike(post_id=post_id, author_id=me['id']))
            else:
                db.execute('DELETE FROM community_likes WHERE post_id=? AND author_id=?', (post_id, me['id']))
        return _view(db, post, me['id'] if me else None)


def vote(path, owner, post_id, option_id):
    from app.models import CommunityVote

    with owner_lock(path, owner), closing(connect_db(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        post = _post(db, post_id)
        if post['kind'] not in ('poll', 'buy'):
            raise HTTPException(400, '这篇帖子不是投票。')
        if not db.execute('SELECT 1 FROM community_poll_options WHERE id=? AND post_id=?', (option_id, post_id)).fetchone():
            raise HTTPException(404, '投票选项不存在。')
        me = _author(db, owner, True)
        previous = db.execute('SELECT option_id FROM community_votes WHERE post_id=? AND author_id=?', (post_id, me['id'])).fetchone()
        if previous and previous['option_id'] != option_id:
            raise HTTPException(409, '你已投过票，提交后不能改票。')
        if not previous:
            _insert(db, 'community_votes', CommunityVote(post_id=post_id, author_id=me['id'], option_id=option_id))
        return _view(db, post, me['id'])


def _comment_view(db, row, viewer):
    from app.models import CommunityCommentView

    author = db.execute('SELECT id,nickname FROM community_authors WHERE id=?', (row['author_id'],)).fetchone()
    return CommunityCommentView(id=row['id'], author=CommunityAuthorView(**dict(author)), text=row['text'],
                                created_at=row['created_at'], can_delete=viewer == row['author_id'])


def list_comments(path, owner, post_id, cursor=None, limit=20):
    from app.models import CommunityComments

    position = _decode_cursor(cursor)
    with closing(connect_db(path)) as db:
        db.execute('BEGIN')
        _post(db, post_id)
        me = _author(db, owner)
        args = [post_id]
        query = 'SELECT * FROM community_comments WHERE post_id=?'
        if position:
            query += ' AND (created_at,id)<(?,?)'
            args.extend(position)
        rows = db.execute(query+' ORDER BY created_at DESC,id DESC LIMIT ?', (*args, limit+1)).fetchall()
        return CommunityComments(comments=[_comment_view(db, r, me['id'] if me else None) for r in rows[:limit]],
                                 next_cursor=_encode_cursor(rows[limit-1]) if len(rows) > limit else None)


def add_comment(path, owner, post_id, draft):
    from app.models import CommunityComment

    with owner_lock(path, owner), closing(connect_db(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        _post(db, post_id)
        me = _author(db, owner, True)
        old = db.execute('SELECT * FROM community_comments WHERE author_id=? AND client_id=?', (me['id'], str(draft.client_id))).fetchone()
        if old:
            if old['post_id'] != post_id or old['text'] != draft.text:
                raise HTTPException(409, '同一条评论的内容已变化，请重新提交。')
            return _comment_view(db, old, me['id']), True
        comment = CommunityComment(id='R'+uuid4().hex, post_id=post_id, author_id=me['id'], text=draft.text, client_id=str(draft.client_id))
        _insert(db, 'community_comments', comment)
        row = db.execute('SELECT * FROM community_comments WHERE id=?', (comment.id,)).fetchone()
        return _comment_view(db, row, me['id']), False


def delete_comment(path, owner, comment_id):
    with owner_lock(path, owner), closing(connect_db(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        me = _author(db, owner)
        if not me or not db.execute('SELECT 1 FROM community_comments WHERE id=? AND author_id=?', (comment_id, me['id'])).fetchone():
            raise HTTPException(404, '这条评论不存在或不能由你删除。')
        db.execute('DELETE FROM community_comments WHERE id=? AND author_id=?', (comment_id, me['id']))
