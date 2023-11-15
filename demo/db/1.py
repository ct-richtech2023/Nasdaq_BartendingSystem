from sqlalchemy import create_engine, Column, Integer, Float, Boolean, DECIMAL, Enum, \
    Date, DateTime, Time, String, Text, func, or_, and_, ForeignKey
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import random

HOSTNAME = '127.0.0.1'
PORT = '3306'
DATABASE = 'first_sqlalchemy'
USERNAME = 'root'
PASSWORD = 'root'

DB_URI = "postgresql://postgres:richtech@{}:5432".format(HOSTNAME)
# DB_URI ="mysql+pymysql://{username}:{password}@{host}:{port}/{db}?charset=utf8".format(username=USERNAME,password=PASSWORD,host=HOSTNAME,port=PORT,db=DATABASE)

engine = create_engine(DB_URI)
Base = declarative_base(engine)

session = sessionmaker(engine)()


# 父表/从表
# user/news
class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True, autoincrement=True)
    uname = Column(String(50), nullable=False)

    def __repr__(self):
        return "<User(uname:%s)>" % self.uname


class News(Base):
    __tablename__ = 'news'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)

    """
    1. RESTRICT：若子表中有父表对应的关联数据，删除父表对应数据，会阻止删除。默认项
    2. NO ACTION：在MySQL中，同RESTRICT。
    3. CASCADE：级联删除。
    4. SET NULL：父表对应数据被删除，子表对应数据项会设置为NULL。"""
    # uid = Column(Integer,ForeignKey("user.id",ondelete='RESTRICT'))
    # uid = Column(Integer,ForeignKey("user.id",ondelete='NO ACTION'))
    # uid = Column(Integer,ForeignKey("user.id",ondelete='CASCADE'))
    uid = Column(Integer, ForeignKey("user.id", ondelete='SET NULL'))

    def __repr__(self):
        return "<News(title:%s,content=%s)>" % (self.title, self.content)


Base.metadata.drop_all()
Base.metadata.create_all()

user = User(uname='momo')
session.add(user)
session.commit()

news1 = News(title='AAA', content='123', uid=1)
news2 = News(title='BBB', content='456', uid=1)
session.add_all([news1, news2])
session.commit()
