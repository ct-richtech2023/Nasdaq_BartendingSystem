# coding:utf8

from sqlalchemy.orm import scoped_session
from sqlalchemy import Column, Integer, String, DateTime, TIMESTAMP, DECIMAL, func, Text, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import ForeignKey, Boolean, create_engine, MetaData, Constraint
from sqlalchemy.orm import relationship, backref, sessionmaker
from sqlalchemy import event

Base = declarative_base()


class Role(Base):  # 一
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    name = Column(String(36), nullable=True)
    users = relationship('User', backref='role')


class User(Base):  # 多
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(36), nullable=True)
    role_id = Column(Integer, ForeignKey('roles.id'))


class Database():
    def __init__(self, bind, pool_size=100, pool_recycle=3600, echo=False):
        self.__engine = create_engine(bind, pool_size=pool_size,
                                      pool_recycle=pool_recycle,
                                      echo=echo)
        self.__session_factory = sessionmaker(bind=self.__engine)
        self.__db_session = scoped_session(self.__session_factory)
        Base.metadata.create_all(self.__engine)

    @property
    def session(self):
        return self.__db_session()


def on_created(target, value, initiator):
    print("received append event for target: %s" % target)


@event.listens_for(User, 'after_insert')
def receive_after_insert(mapper, connection, target):
    print("insert.......")


SQLALCHEMY_DATABASE_URL = "postgresql://postgres:richtech@{}:5432".format('127.0.0.1')

db = Database(bind=SQLALCHEMY_DATABASE_URL)

if __name__ == "__main__":
    user = User()
    user.name = "123"
    user.role_id = 2
    db.session.add(user)
    db.session.commit()
