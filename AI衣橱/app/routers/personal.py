from contextlib import closing
from typing import Annotated, Literal

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response

from app.db import connect_db
from app.models import (
    PersonalCheckinView,
    PersonalFeedbackDraft,
    PersonalInput,
    PersonalPage,
    PersonalPointsView,
    PersonalSettingsPatch,
    PersonalTicketView,
)
from app.routers.wardrobe import Database, Owner
from app.services import personal

router=APIRouter(prefix='/api/me',tags=['我的'])
Cursor=Annotated[str|None,Query(max_length=512)]
Limit=Annotated[int,Query(ge=1,le=20)]


@router.post('/points/check-in',response_model=PersonalCheckinView)
def checkin(path:Database,owner:Owner,body:Annotated[dict|None,Body()]=None):
    if body:
        raise HTTPException(400,'积分由服务端计算，无需提交参数。')
    return personal.check_in(path,owner)


@router.get('/points',response_model=PersonalPointsView)
def points(path:Database,owner:Owner,cursor:Cursor=None,limit:Limit=20):
    return personal.points(path,owner,cursor,limit)


@router.post('/write-tickets',response_model=PersonalTicketView)
def ticket(path:Database,owner:Owner,purpose:Literal['ootd','feedback','avatar','settings','favorite']):
    return personal.issue_ticket(path,owner,purpose)


@router.get('')
def overview(path:Database,owner:Owner):
    return personal.overview(path,owner)


@router.get('/content',response_model=PersonalPage)
def content(path:Database,owner:Owner,tab:Literal['history','favorites','published','outfits'],cursor:Cursor=None,limit:Limit=20,status:Literal['all','processing','completed','failed']='all'):
    return personal.content(path,owner,tab,cursor,limit,status)


@router.get('/outfits/{oid}')
def outfit(oid:str,path:Database,owner:Owner):
    with closing(connect_db(path)) as db:
        return personal.outfit_view(db,owner,oid)


@router.get('/people',response_model=PersonalPage)
def people(path:Database,owner:Owner,tab:Literal['following','followers'],cursor:Cursor=None,limit:Limit=20):
    return personal.people(path,owner,tab,cursor,limit)


@router.get('/authors/{author}/posts',response_model=PersonalPage)
def author_posts(author:str,path:Database,owner:Owner,cursor:Cursor=None,limit:Limit=20):
    return personal.author_posts(path,owner,author,cursor,limit)


@router.get('/interactions',response_model=PersonalPage)
def interactions(path:Database,owner:Owner,cursor:Cursor=None,limit:Limit=20):
    return personal.interactions(path,owner,cursor,limit)


@router.get('/favorites/{pid}')
def favorite_status(pid:str,path:Database,owner:Owner):
    return personal.favorite(path,owner,pid)


@router.put('/favorites/{pid}')
def favorite(pid:str,body:PersonalInput,path:Database,owner:Owner):
    return personal.favorite(path,owner,pid,body.ticket,True)


@router.delete('/favorites/{pid}')
def unfavorite(pid:str,body:PersonalInput,path:Database,owner:Owner):
    return personal.favorite(path,owner,pid,body.ticket,False)


@router.patch('/settings')
def settings(body:PersonalSettingsPatch,path:Database,owner:Owner):
    return personal.settings(path,owner,body)


@router.get('/avatar')
def avatar_photo(path:Database,owner:Owner):
    data,mime=personal.avatar_photo(path,owner)
    return Response(data,media_type=mime,headers={'X-Content-Type-Options':'nosniff'})


@router.put('/avatar')
def avatar(path:Database,owner:Owner,ticket:Annotated[str,Form(max_length=2048)],photo:Annotated[UploadFile,File()]):
    return personal.avatar(path,owner,ticket,photo.file.read(2*1024*1024+1))


@router.delete('/avatar')
def remove_avatar(body:PersonalInput,path:Database,owner:Owner):
    return personal.avatar(path,owner,body.ticket,remove=True)


@router.post('/feedback')
def feedback(body:PersonalFeedbackDraft,path:Database,owner:Owner):
    value,reused=personal.feedback(path,owner,body)
    return JSONResponse(status_code=200 if reused else 201,content=value)


@router.get('/tryons/{task_id}')
def historical_tryon(task_id:str,path:Database,owner:Owner):
    return personal.historical_tryon(path,owner,task_id)
