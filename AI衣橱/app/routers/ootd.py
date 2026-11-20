from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.models import OotdDraft, OotdPatch, PersonalPage
from app.routers.personal import Cursor, Limit
from app.routers.wardrobe import Database, Owner
from app.services import ootd

router=APIRouter(prefix='/api/me/ootds',tags=['私密穿搭日记'])


@router.get('',response_model=PersonalPage)
def listing(path:Database,owner:Owner,cursor:Cursor=None,limit:Limit=20):
    return ootd.listing(path,owner,cursor,limit)


@router.post('')
def create(path:Database,owner:Owner,metadata:Annotated[str,Form(max_length=8000)],photo:Annotated[UploadFile|None,File()]=None):
    try:
        draft=OotdDraft.model_validate_json(metadata)
    except ValidationError:
        raise HTTPException(400,'请检查日期、照片来源和文字长度。') from None
    data=photo.file.read(10*1024*1024+1) if photo else None
    value,reused=ootd.create(path,owner,draft,data)
    return JSONResponse(status_code=200 if reused else 201,content=value)


@router.get('/{oid}')
def get(oid:str,path:Database,owner:Owner):
    return ootd.get(path,owner,oid)


@router.patch('/{oid}')
def update(oid:str,patch:OotdPatch,path:Database,owner:Owner):
    return ootd.update(path,owner,oid,patch)


@router.delete('/{oid}',status_code=204)
def delete(oid:str,path:Database,owner:Owner):
    ootd.delete(path,owner,oid)
    return Response(status_code=204)


@router.get('/{oid}/photo')
def photo(oid:str,path:Database,owner:Owner):
    data,mime=ootd.photo(path,owner,oid)
    return Response(data,media_type=mime,headers={'X-Content-Type-Options':'nosniff'})
