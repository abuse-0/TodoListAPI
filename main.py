# uvicorn main:app --reload
# http://127.0.0.1:8000/docs
# http://127.0.0.1:8000

import uvicorn
import hashlib
import jwt
import datetime

from fastapi import FastAPI, HTTPException, Header, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine
from typing import Annotated

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import update, delete


# подключение
#postgresql://имя:пароль@хост/имя бд, логи
engine = create_engine('postgresql://postgres:1234@localhost/postgres')#, echo=True)

# создание таблицы и столбцов, если их нет. 
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(30))
    email = Column(String(30))
    password = Column(String(300))

class ToDoList(Base):
    __tablename__ = 'to_do_list'

    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    description = Column(String(500))
    user_id = Column(Integer)


# Сам проверяет, есть ли таблица
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

# Валидации
class UserRegister(BaseModel):
    name: str = Field(min_length=3)
    email: EmailStr
    password: str = Field(min_length=4)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4)


class ToDo(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    description: str = Field(max_length=500)


app = FastAPI()

def hash_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()

def register_write_to_db(name: str, email: str, password: str) -> None:
    # Тут создается экземляр класса User
    existing_user = session.query(User).filter_by(email=email).first()
    # Прерывает функцию
    if existing_user:
        raise ValueError("Пользователь с таким email уже существует")

    new_user = User(name=name, email=email, password=password)
    session.add(new_user)
    session.commit()

def create_token(id: int, email: str) -> str:
    id = session.query(User).filter_by(email=email).first().id
    secret_key = "secret_key"

    payload = {
        "user_id": id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }

    return jwt.encode(payload, secret_key, algorithm='HS256')


# А как собственно время то проверять... как вот так отправить "message": "Unauthorized"
# Как адекватно исключения не все, а определенное ловить
def verify_token(token: str) -> int | None:
    secret_key = "secret_key"
    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        print(payload)
        return payload['user_id']
    except:
        return None


# Вернет токен с айди
@app.post("/register")
def register(user: UserRegister) -> dict[str, str]:
    name = user.name
    email = user.email
    password = user.password
    hashed_password = hash_password(password)

    # Запись в бд
    register_write_to_db(name, email, hashed_password)

    token = create_token(id, email)
    print(token)

    return {"token": token}


@app.post("/login")
def login(user: UserLogin) -> dict[str, str]:
    email = user.email
    login_password = user.password

    db_user = session.query(User).filter_by(email=email).first()
    if db_user is None or hash_password(login_password) != db_user.password:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    token = create_token(db_user.id, email)
    print(token)
    return {"token": token}


@app.post("/todos")
# Если я тут напишу -> ditc[str, str] все сломается
def todo(todo: ToDo, token: Annotated[str, Header()]):
    title = todo.title
    description = todo.description

    flag = verify_token(token) # id/None

    # Подход не из лучших конечно с title=title
    if flag:
        new_todo = ToDoList(title=title, description=description, user_id=flag)
        session.add(new_todo)
        session.commit()
        todo_id = session.query(ToDoList).filter_by(title=title).first().id

        return {
            "id": todo_id,
            "title": title,
            "description": description,
            "user_id": flag
        }
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.put("/todos/{todo_id}")
async def update_todo(todo_id: int, todo: ToDo, token: Annotated[str, Header()]):
    title = todo.title
    description = todo.description

    flag = verify_token(token)

    user_id = session.query(ToDoList).filter_by(id=todo_id).first().user_id

    if flag == user_id:
        stmt = (
            update(ToDoList)
            # Тут вместо and юзается запятая
            .where(ToDoList.user_id == flag, ToDoList.id == todo_id)
            .values(title=title, description=description)
        )

        session.execute(stmt)
        session.commit()
    
        return {
            "id": todo_id,
            "title": title,
            "description": description
        }
    else:
        raise HTTPException(status_code=403, detail="Forbidden")
    
@app.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: int, todo: ToDo, token: Annotated[str, Header()]):
    flag = verify_token(token)

    if flag:
        stmt = delete(ToDoList).where(ToDoList.id == todo_id)
        session.execute(stmt)
        session.commit()

# GET /todos?page=1&limit=10
@app.get("/todos")
async def get_todo(token: Annotated[str, Header()], page: int = Query(alias="page"), limit: int = Query(alias="limit")):
    flag = verify_token(token)

    if flag:
        # Я должен написать эквивалент SELECT * FROM to_do_list
        # Затем циклов while n == limit or len(to_do_list) == 0(тоже в переменной хранить), len_list = len(to_do_list), len_list -= 1
        # Добавлять это в словарь , вида 

        """
        {
          "data": [
            {
              "id": 1,
              "title": "Buy groceries",
              "description": "Buy milk, eggs, bread"
            },
            {
              "id": 2,
              "title": "Pay bills",
              "description": "Pay electricity and water bills"
            }
          ],
          "page": 1,
          "limit": 10,
          "total": 2
        }                
        """
        todos = session.query(ToDoList).all()
        total = 0

        result = {
          "data": [
          ],
          "page": 1,
          "limit": limit,
          "total": total 
        }  

        for todo in todos:
            if limit == 0:
                break

            todo = {
            "id": todo.id,
            "title": todo.title,
            "description": todo.description
            }
            
            print(todo)
            result["data"].append(todo)
            limit -= 1
            result['total'] += 1

        return result



if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="info")





