from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.models import (
    CommunityCommentDraft,
    CommunityComments,
    CommunityCommentView,
    CommunityDraft,
    CommunityFeed,
    CommunityPostView,
    CommunityTab,
    CommunityVoteDraft,
)
from app.routers.wardrobe import Database, Owner
from app.services import community

router = APIRouter(prefix='/api/community', tags=['应用内社区'])


@router.get('/posts', response_model=CommunityFeed)
def posts(path: Database, owner: Owner, tab: CommunityTab = 'all',
          cursor: Annotated[str | None, Query(max_length=256)] = None,
          limit: Annotated[int, Query(ge=1, le=20)] = 20):
    return community.list_posts(path, owner, tab, cursor, limit)


@router.get('/posts/{post_id}', response_model=CommunityPostView)
def post(post_id: str, path: Database, owner: Owner):
    return community.get_post(path, owner, post_id)


@router.post('/posts', response_model=CommunityPostView, status_code=201)
def publish(path: Database, owner: Owner, metadata: Annotated[str, Form(max_length=10000)],
            photos: Annotated[list[UploadFile] | None, File()] = None):
    try:
        draft = CommunityDraft.model_validate_json(metadata)
    except ValidationError:
        raise HTTPException(422, '发布内容无效，请检查标题、图片及投票选项。') from None
    if len(photos or []) > 9:
        raise HTTPException(422, '每帖最多9张照片。')
    images = []
    for image in photos or []:
        data = image.file.read(community.MAX_IMAGE+1)
        mime, _ = community._image(data)
        if image.content_type != mime:
            raise HTTPException(422, '图片类型与内容不一致，请重新选择。')
        images.append(data)
    result, reused = community.publish(path, owner, draft, images)
    return JSONResponse(status_code=200 if reused else 201, content=result.model_dump(mode='json'))


@router.delete('/posts/{post_id}', status_code=204)
def delete(post_id: str, path: Database, owner: Owner):
    community.delete_post(path, owner, post_id)
    return Response(status_code=204)


@router.get('/posts/{post_id}/photos/{media_id}')
def photo(post_id: str, media_id: str, path: Database, owner: Owner):
    image, mime = community.photo_file(path, post_id, media_id)
    try:
        data = image.read_bytes()
    except OSError:
        raise HTTPException(404, '帖子照片不存在。') from None
    return Response(data, media_type=mime, headers={'X-Content-Type-Options': 'nosniff'})


@router.put('/authors/{author_id}/follow')
def follow(author_id: str, path: Database, owner: Owner):
    return community.follow_author(path, owner, author_id, True)


@router.delete('/authors/{author_id}/follow')
def unfollow(author_id: str, path: Database, owner: Owner):
    return community.follow_author(path, owner, author_id, False)


@router.put('/posts/{post_id}/like', response_model=CommunityPostView)
def like(post_id: str, path: Database, owner: Owner):
    return community.like_post(path, owner, post_id, True)


@router.delete('/posts/{post_id}/like', response_model=CommunityPostView)
def unlike(post_id: str, path: Database, owner: Owner):
    return community.like_post(path, owner, post_id, False)


@router.put('/posts/{post_id}/vote', response_model=CommunityPostView)
def vote(post_id: str, body: CommunityVoteDraft, path: Database, owner: Owner):
    return community.vote(path, owner, post_id, body.option_id)


@router.get('/posts/{post_id}/comments', response_model=CommunityComments)
def comments(post_id: str, path: Database, owner: Owner,
             cursor: Annotated[str | None, Query(max_length=256)] = None,
             limit: Annotated[int, Query(ge=1, le=20)] = 20):
    return community.list_comments(path, owner, post_id, cursor, limit)


@router.post('/posts/{post_id}/comments', response_model=CommunityCommentView, status_code=201)
def comment(post_id: str, body: CommunityCommentDraft, path: Database, owner: Owner):
    result, reused = community.add_comment(path, owner, post_id, body)
    return JSONResponse(status_code=200 if reused else 201, content=result.model_dump(mode='json'))


@router.delete('/comments/{comment_id}', status_code=204)
def remove_comment(comment_id: str, path: Database, owner: Owner):
    community.delete_comment(path, owner, comment_id)
    return Response(status_code=204)
