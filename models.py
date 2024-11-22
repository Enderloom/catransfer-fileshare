# models.py

from sqlalchemy import Table, Column, Integer, String
from database import metadata

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String, unique=True, index=True, nullable=False),
    Column("email", String, unique=True, index=True, nullable=False),
    Column("hashed_password", String, nullable=False),
    Column("user_id", String, unique=True, index=True, nullable=False),
)
