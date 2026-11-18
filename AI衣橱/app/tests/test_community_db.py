import sqlite3

import pytest

from app.db import connect_db, init_db, to_db_values
from app.models import CommunityAuthor, CommunityOption, CommunityPost, CommunityVote


def insert(db, table, item):
    row = to_db_values(item)
    db.execute(f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join(':'+x for x in row)})", row)


def test_community_migration_idempotent_sources_and_owner_unique(tmp_path):
    path = tmp_path / 'app.db'
    init_db(path)
    a = CommunityAuthor(id='a', owner_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', nickname='衣友a')
    with connect_db(path) as db, db:
        insert(db, 'community_authors', a)
        with pytest.raises(sqlite3.IntegrityError):
            insert(db, 'community_authors', a.model_copy(update={'id': 'b'}))
    init_db(path)
    init_db(path)
    with connect_db(path) as db:
        assert db.execute('select count(*) from community_authors').fetchone()[0] == 1
        assert not db.execute('pragma foreign_key_check').fetchall()
        assert a.sources['owner_id'] == 'derived'


def test_community_vote_option_ownership_and_unique(tmp_path):
    path = tmp_path / 'app.db'
    init_db(path)
    with connect_db(path) as db, db:
        insert(db, 'community_authors', CommunityAuthor(id='a', owner_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', nickname='衣友a'))
        for post_id in ['p', 'q']:
            insert(db, 'community_posts', CommunityPost(id=post_id, author_id='a', kind='buy', title='值得买吗', draft_id=post_id, request_hash='a'*64))
            insert(db, 'community_poll_options', CommunityOption(id=post_id+'o', post_id=post_id, position=0, label='值得'))
        with pytest.raises(sqlite3.IntegrityError):
            insert(db, 'community_votes', CommunityVote(post_id='p', author_id='a', option_id='qo'))
        vote = CommunityVote(post_id='p', author_id='a', option_id='po')
        insert(db, 'community_votes', vote)
        with pytest.raises(sqlite3.IntegrityError):
            insert(db, 'community_votes', vote)
        db.execute("delete from community_posts where id='p'")
        assert db.execute('select count(*) from community_votes').fetchone()[0] == 0
