"""Base déclarative et types communs (compatibles MySQL en production, SQLite en test)."""
from sqlalchemy import BigInteger, Integer, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase

# INT UNSIGNED sous MySQL, INTEGER sous SQLite
UInt = Integer().with_variant(mysql.INTEGER(unsigned=True), "mysql")
# BIGINT UNSIGNED sous MySQL ; INTEGER sous SQLite (nécessaire pour l'auto-incrément)
UBigInt = BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(Integer, "sqlite")
# LONGTEXT sous MySQL
LongText = Text().with_variant(mysql.LONGTEXT(), "mysql")


class Base(DeclarativeBase):
    pass
