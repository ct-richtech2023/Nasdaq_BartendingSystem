from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field

Base = declarative_base()


class SimpleOrm(Base):
    __tablename__ = 'simples'
    three_words_id = Column(String, primary_key=True)


class SimpleModel(BaseModel):
    three_words_id: str = Field(..., alias="threeWordsId")

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
        # allow_population_by_alias = True # in case pydantic.version.VERSION < 1.0


simple_orm = SimpleOrm(three_words_id='abc')
simple_oops = SimpleModel.from_orm(simple_orm)

print(simple_oops.json())  # {"three_words_id": "abc"}
print(simple_oops.json(by_alias=True))  # {"threeWordsId": "abc"}

from fastapi import FastAPI

app = FastAPI()


@app.get("/model", response_model=SimpleModel)
def get_model():
    # results in {"threeWordsId":"abc"}
    return SimpleOrm(three_words_id='abc')


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app)
