from typing import List

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel
from starlette.responses import RedirectResponse

app = FastAPI()


@app.get("/", include_in_schema=False)
async def root(request: Request):
    docs_url = "{}docs".format(request.url)
    return RedirectResponse(url=docs_url)


class Table(BaseModel):
    cardNo: str
    tableName: str


class Data(BaseModel):
    cardNoInfos: List[Table]
    uuid: str
    idForBox: str


a = {
    "cardNoInfos": [{"cardNo": "2", "tableName": "A06"}],
    "uuid": "653aeca0-8e3e-11eb-9d15-457cbb825139",
    "idForBox": "25432"
}


@app.post("/resp")
def resp(data: Data):
    print(data)
    return "received"


if __name__ == '__main__':
    uvicorn.run(app="main:app", host='0.0.0.0', port=5000)
