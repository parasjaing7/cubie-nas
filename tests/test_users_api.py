from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
from fastapi import HTTPException

from app.db import Base
from app.models import User
from app.routers import users
from app.schemas import UserUpdateRequest
from app.security import hash_password


def _db_session():
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def test_update_app_user_changes_role_and_password():
    db = _db_session()
    try:
        user = User(username='alice', password_hash=hash_password('oldpass123'), role='user')
        admin = User(username='admin', password_hash=hash_password('adminpass123'), role='admin')
        old_hash = user.password_hash
        db.add_all([user, admin])
        db.commit()

        users.update_app_user(
            'alice',
            UserUpdateRequest(role='admin', new_password='newpass123'),
            _=admin,
            db=db,
        )

        updated = db.query(User).filter(User.username == 'alice').first()
        assert updated is not None
        assert updated.role == 'admin'
        assert updated.password_hash != old_hash
    finally:
        db.close()


def test_delete_app_user_removes_target_user():
    db = _db_session()
    try:
        victim = User(username='victim', password_hash=hash_password('victimpass123'), role='user')
        admin = User(username='admin', password_hash=hash_password('adminpass123'), role='admin')
        db.add_all([victim, admin])
        db.commit()

        users.delete_app_user('victim', current_user=admin, db=db)

        missing = db.query(User).filter(User.username == 'victim').first()
        assert missing is None
    finally:
        db.close()


def test_delete_app_user_rejects_current_admin():
    db = _db_session()
    try:
        admin = User(username='admin', password_hash=hash_password('adminpass123'), role='admin')
        db.add(admin)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            users.delete_app_user('admin', current_user=admin, db=db)

        assert exc.value.status_code == 400
    finally:
        db.close()
