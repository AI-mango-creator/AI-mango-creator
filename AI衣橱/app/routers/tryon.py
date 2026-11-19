from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.models import ExperienceProductView, TryonTicket, TryonView
from app.routers.wardrobe import Database, Owner
from app.services import tryon

router = APIRouter(tags=['试穿体验'])
ProductId = Annotated[str, Query(min_length=1, max_length=80)]


@router.get('/api/experience/products', response_model=list[ExperienceProductView])
def products(path: Database, owner: Owner):
    return tryon.products(path)


@router.get('/api/experience/products/{product_id}', response_model=ExperienceProductView)
def product(product_id: str, path: Database, owner: Owner):
    return ExperienceProductView(**tryon.product(path, product_id))


@router.get('/api/experience/products/{product_id}/photo')
def product_photo(product_id: str, path: Database, owner: Owner):
    data, mime = tryon.product_photo(path, product_id)
    return Response(data, media_type=mime, headers={'X-Content-Type-Options': 'nosniff'})


@router.get('/api/tryons/ticket', response_model=TryonTicket)
def ticket(product_id: ProductId, path: Database, owner: Owner):
    return tryon.ticket(path, owner, product_id)


@router.post('/api/tryons', response_model=TryonView, status_code=202)
def create(path: Database, owner: Owner, product_id: Annotated[str, Form(max_length=80)],
           ticket: Annotated[str, Form(max_length=2048)], consent: Annotated[bool, Form()], photo: Annotated[UploadFile, File()]):
    data = photo.file.read(10*1024*1024+1)
    if len(data)>10*1024*1024:
        raise HTTPException(413, '照片超过10MB，请选择较小图片。')
    return tryon.create(path, owner, product_id, ticket, data, consent)


@router.get('/api/tryons', response_model=list[TryonView])
def recent(product_id: ProductId, path: Database, owner: Owner):
    return tryon.recent(path, owner, product_id)


@router.get('/api/tryons/{task_id}', response_model=TryonView)
def get(task_id: str, path: Database, owner: Owner):
    return tryon.get(path, owner, task_id)


@router.get('/api/tryons/{task_id}/result')
def result(task_id: str, path: Database, owner: Owner):
    data, mime = tryon.result_photo(path, owner, task_id)
    return Response(data, media_type=mime, headers={'X-Content-Type-Options': 'nosniff'})


@router.delete('/api/tryons/{task_id}', status_code=204)
def delete(task_id: str, path: Database, owner: Owner):
    tryon.delete(path, owner, task_id)
    return Response(status_code=204)
