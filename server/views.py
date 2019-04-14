from .models import db, Client, Film
import jwt
import time
from .wsgi import app
from flask import request, Request, Response, redirect, url_for
from typing import List

import enum


class TokenState(enum.Enum):
    Valid = 1
    Invalid = 2
    Expired = 3


from functools import wraps


def jwt_token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token_state = get_token_state()
        if token_state == TokenState.Invalid:
            r = lambda *args: "Invalid token"
            return r(*args)
        elif token_state == TokenState.Expired:
            r = lambda *args: "Invalid expired"
            return r(*args)
        else:
            return f(*args, **kwargs)

    return decorated_function


def get_token_state() -> TokenState:
    access_token = request.form.get('access_token', None)
    if not access_token:
        return TokenState.Invalid
    access_token = access_token.encode()
    try:
        decoded = jwt.decode(access_token, app.secret_key, algorithms=['HS256'])
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        return TokenState.Invalid
    client_id = decoded.get('client_id', None)
    if client_id is None:
        return TokenState.Invalid
    client = Client.query.get(client_id)
    return TokenState.Valid if access_token.decode() == client.access_token else TokenState.Invalid


def wrap_into_json(data: List[object]):
    return str(data)


def create_client(request: Request) -> str:
    login = request.form.get('login', None)
    password = request.form.get('password', None)
    email = request.form.get('email', None)
    if not login or not password or not email:
        return "Not enught data"
    new_client = Client(login, email, password)
    db.session.add(new_client)
    db.session.commit()
    return "{} created".format(login)


def update_client(request: Request, user_id: int) -> str:
    client = Client.query.get(user_id)
    login = request.form.get('login', None)
    password = request.form.get('password', None)
    email = request.form.get('email', None)
    if not login or not password or not email:
        return "Not enught data"

    if login:
        client.login = login
    if password:
        client.password = password
    if email:
        client.email = email
    db.session.add(client)
    db.session.commit()
    return "updated"


@app.route('/api/1/users', methods=['GET', 'POST'])
@jwt_token_required
def handle_users():
    if request.method == 'GET':
        clients = Client.query.all()
        return wrap_into_json(clients)
    if request.method == 'POST':
        login = create_client(request)
        return login


@app.route('/api/1/users/<user_id>', methods=['GET', 'DELETE', 'PUT'])
@jwt_token_required
def handle_user(user_id):
    if request.method == 'GET':
        client = Client.query.get(user_id)
        return str(client.login)
    if request.method == 'DELETE':
        client = Client.query.get(user_id)
        db.session.delete(client)
        db.session.commit()
        return "deleted"
    if request.method == 'PUT':
        response = update_client(request, user_id)
        return response


def create_film(request: Request):
    film_name = request.form.get('film_name', None)
    creation_year = request.form.get('creation_year', None)
    creation_country = request.form.get('creation_country', None)
    if not film_name or not creation_year or not creation_country:
        return "Not enught data"
    new_film = Film(film_name, creation_year, creation_country)
    db.session.add(new_film)
    db.session.commit()
    return "{} created".format(film_name)


def update_film(request: Request, film_id: int):
    film = Film.query.get(film_id)
    film_name = request.form.get('film_name', None)
    creation_year = request.form.get('creation_year', None)
    creation_country = request.form.get('creation_country', None)
    if not film_name or not creation_year or not creation_country:
        return "Not enught data"

    if film_name:
        film.film_name = film_name
    if creation_year:
        film.creation_year = creation_year
    if creation_country:
        film.creation_country = creation_country
    db.session.add(film)
    db.session.commit()
    return "updated"


@app.route('/api/1/films', methods=['GET', 'POST'])
@jwt_token_required
def handle_films():
    if request.method == 'GET':
        films = Film.query.all()
        return wrap_into_json(films)
    if request.method == 'POST':
        response = create_film(request)
        return response


@app.route('/api/1/films/<film_id>', methods=['GET', 'DELETE', 'PUT'])
@jwt_token_required
def handle_film(film_id):
    if request.method == 'GET':
        film = Film.query.get(film_id)
        return str(film.film_name)
    if request.method == 'DELETE':
        film = Film.query.get(film_id)
        db.session.delete(film)
        db.session.commit()
        return "deleted"
    if request.method == 'PUT':
        response = update_film(request, film_id)
        return response


@app.route('/api/1/assessment', methods=['POST'])
@jwt_token_required
def make_assessment():
    client_id = request.form.get('client_id', None)
    film_id = request.form.get('film_id', None)
    assessment_value = request.form.get('assessment_value', None)
    if not client_id or not film_id or not assessment_value:
        return "not enough data"

    client = Client.query.get(client_id)
    film = Film.query.get(film_id)
    response = client.make_assessment(assessment_value, film)
    return response


@app.route('/api/1/assessment/<user_id>', methods=['GET'])
@jwt_token_required
def get_assessnent(user_id):
    client = Client.query.get(user_id)
    return wrap_into_json(client.assessments)
    # return wrap_into_json(Response('<Why access is denied string goes here...>', 401, {'WWW-Authenticate':'Basic realm="Login Required"'}))


def generate_token(client: Client, for_access=False) -> str:
    return jwt.encode(
        {
            'client_id': str(client.id),
            'exp': str(int(time.time()) + (1800 if for_access else (86400 * 30)))
        },
        app.secret_key,
        algorithm='HS256'
    )


@app.route('/api/1/login')
def login():
    login = request.form.get('login', None)
    password = request.form.get('password', None)
    if not login or not password:
        return "not enought data"
    client = Client.query.filter_by(login=login).first()
    if client and client.verify_password(password):
        client.access_token = generate_token(client).decode()
        client.refresh_token = generate_token(client, for_access=False).decode()

        db.session.add(client)
        db.session.commit()
        return str({
            'access_token': client.access_token,
            'refresh_token': client.refresh_token
        })
    else:
        return 'User not exist'


@app.route('/api/1/refresh_token')
def refresh_token():
    refresh_token = request.form.get('refresh_token', None)
    client_id = request.form.get('client_id', None)
    client = Client.query.get(client_id)
    if client.refresh_token == refresh_token:
        client.access_token = generate_token(client).decode()
        client.refresh_token = generate_token(client, for_access=False).decode()
        db.session.add(client)
        db.session.commit()
        return "Refreshing success"
    else:
        return "Invalid refresh token"
