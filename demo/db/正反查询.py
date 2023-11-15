# coding:utf-8

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DATE, ForeignKey  # 导入外键
from sqlalchemy.orm import relationship  # 创建关系

DB_URI = "postgresql://postgres:richtech@{}:5432".format('127.0.0.1')

engine = create_engine(DB_URI, encoding="utf-8")

Base = declarative_base()  # 生成orm基类


class Company(Base):
    __tablename__ = "company"

    name = Column(String(20), primary_key=True)
    location = Column(String(20))

    def __repr__(self):
        return "name:{0} location:{1}".format(self.name, self.location)


class Phone(Base):
    __tablename__ = "phone"

    id = Column(Integer, primary_key=True)
    model = Column(String(32))
    price = Column(String(32))
    company_name = Column(String(32), ForeignKey("company.name"))
    company = relationship("Company", backref="phone_of_company")

    def __repr__(self):
        return "id:{0},model:{1} price:{2} company_name:{3}".format(self.id, self.model, self.price, self.company_name)


Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)  # 创建表

# coding:utf-8

from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.mysql import INTEGER, CHAR
from sqlalchemy import create_engine, Column


def insert(new_data):
    # Base = declarative_base()  # 修改用户名、密码、数据库的名字
    # engine = create_engine('mysql+mysqldb://root:123@localhost:3306/test')
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    session.add(new_data)
    session.commit()
    session.close()


#


# coding:utf-8


companys = {
    "Apple": "Amercian",
    "Xiaomi": "China",
    "Huawei": "China",
    "SungSum": "Korea",
    "Nokia": "Finland"
}
phones = (
    [1, "iphoneX", "Apple", 8400],
    [2, "xiaomi2s", "Xiaomi", 3299],
    [3, "Huaweimate10", "Huawei", 3399],
    [4, "SungsumS8", "SungSum", 4099],
    [5, "NokiaLumia", "Nokia", 2399],
    [6, "iphone4s", "Apple", 3800]
)

for key in companys:
    new_company = Company(name=key, location=companys[key])
    insert(new_company)

for phone in phones:
    id = phone[0]
    model = phone[1]
    company_name = phone[2]
    price = phone[3]

    new_phone = Phone(id=id, model=model, company_name=company_name, price=price)
    insert(new_phone)

# 无法添加这个条目，因为外键约束了，公司表中没有BlackBerry就不能添加
# new_phone = Phone(id=7, model="BlackBerry", company_name="RIM", price=3200)
# insert(new_phone)


# relationship 是 sqlalchemy 自己做的查询优化
# https://www.cnblogs.com/goldsunshine/p/9269880.html
# 1、正向查询
# 查询phone表
DBSession = sessionmaker(bind=engine)
session = DBSession()
phone_obj = session.query(Phone).filter_by(id=1).first()
# 通过phone表关联的relationship字段"Company"查询出company表的数据
print(phone_obj.company)

# 2、反向查询
# 查询company表
company_obj = session.query(Company).filter_by(name="Nokia").first()
# 通过phone表关联的relationship的字段"backref="phone_of_company"",查询phone表数据
print(company_obj.phone_of_company)
