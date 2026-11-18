import json
from contextlib import closing

from fastapi import APIRouter

from app.db import connect_db, owner_lock, to_db_values
from app.models import BodyProfile, ProfilePatch
from app.routers.wardrobe import Database, Owner

router = APIRouter(prefix="/api/profile", tags=["身材资料"])


@router.get("", response_model=BodyProfile)
def get_profile(path: Database, owner_id: Owner):
    with closing(connect_db(path)) as db:
        row = db.execute("SELECT * FROM body_profiles WHERE owner_id=?", (owner_id,)).fetchone()
    if row is None:
        return BodyProfile(owner_id=owner_id)
    return BodyProfile.model_validate(dict(row) | {"sources": json.loads(row["sources"])})


@router.patch("", response_model=BodyProfile)
def update_profile(patch: ProfilePatch, path: Database, owner_id: Owner):
    with owner_lock(path, owner_id):
        current = get_profile(path, owner_id)
        profile = BodyProfile.model_validate(current.model_dump() | patch.model_dump(exclude_unset=True))
        values = to_db_values(profile)
        with closing(connect_db(path)) as db, db:
            db.execute("INSERT INTO body_profiles(owner_id,height_cm,weight_kg,body_shape,sources) "
                       "VALUES(:owner_id,:height_cm,:weight_kg,:body_shape,:sources) "
                       "ON CONFLICT(owner_id) DO UPDATE SET height_cm=excluded.height_cm,"
                       "weight_kg=excluded.weight_kg,body_shape=excluded.body_shape,sources=excluded.sources", values)
        return profile
