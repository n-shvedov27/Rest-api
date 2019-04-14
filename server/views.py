from .models import db, Client, Film
import jwt
import time
from .wsgi import app
from flask import request, Request, Response
from typing import List
import json
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
            r = lambda *args: Response("Invalid token", 401)
            return r(*args)
        elif token_state == TokenState.Expired:
            r = lambda *args: Response("Token expired", 401)
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


def create_client(request: Request) -> int:
    login = request.form.get('login', None)
    password = request.form.get('password', None)
    email = request.form.get('email', None)
    if not login or not password or not email:
        return 400
    new_client = Client(login, email, password)
    db.session.add(new_client)
    db.session.commit()
    return 200


def update_client(request: Request, user_id: int) -> int:
    client = Client.query.get(user_id)
    if not client:
        return 403
    login = request.form.get('login', None)
    password = request.form.get('password', None)
    email = request.form.get('email', None)
    if not login or not password or not email:
        return 400
    client.login = login
    client.password = password
    client.email = email
    db.session.add(client)
    db.session.commit()
    return 200


@app.route('/api/1/users', methods=['GET', 'POST'])
@jwt_token_required
def handle_users():
    if request.method == 'GET':
        clients = Client.query.all()
        return Response(json.dumps({'clients': [client.serialize() for client in clients]}), 200)
    if request.method == 'POST':
        creating_status = create_client(request)
        if creating_status == 200:
            return Response("Client was created", 200)
        elif creating_status == 400:
            return Response("Not enough data", 400)


@app.route('/api/1/users/<user_id>', methods=['GET', 'DELETE', 'PUT'])
@jwt_token_required
def handle_user(user_id):
    if request.method == 'GET':
        client = Client.query.get(user_id)
        if not client:
            return Response('Client not exist', 403)
        return Response(json.dumps(client.serialize()), 200)
    if request.method == 'DELETE':
        client = Client.query.get(user_id)
        if not client:
            return Response('Client not exist', 403)
        db.session.delete(client)
        db.session.commit()
        return Response("Client was deleted", 200)
    if request.method == 'PUT':
        updating_status = update_client(request, user_id)
        if updating_status == 200:
            return Response("Client was updated", 200)
        elif updating_status == 403:
            return Response("Client not exist", 403)
        elif updating_status == 400:
            return Response("Not enough data", 400)


def create_film(request: Request):
    film_name = request.form.get('film_name', None)
    creation_year = request.form.get('creation_year', None)
    creation_country = request.form.get('creation_country', None)
    if not film_name or not creation_year or not creation_country:
        return 400
    new_film = Film(film_name, creation_year, creation_country)
    db.session.add(new_film)
    db.session.commit()
    return 200


def update_film(request: Request, film_id: int) -> int:
    film = Film.query.get(film_id)
    film_name = request.form.get('film_name', None)
    creation_year = request.form.get('creation_year', None)
    creation_country = request.form.get('creation_country', None)
    if not film_name or not creation_year or not creation_country:
        return 400

    if film_name:
        film.film_name = film_name
    if creation_year:
        film.creation_year = creation_year
    if creation_country:
        film.creation_country = creation_country
    db.session.add(film)
    db.session.commit()
    return 200


@app.route('/api/1/films', methods=['GET', 'POST'])
@jwt_token_required
def handle_films():
    if request.method == 'GET':
        films = Film.query.all()
        return Response(json.dumps({'films': [film.serialize() for film in films]}), 200)
    if request.method == 'POST':
        creating_status = create_film(request)
        if creating_status == 200:
            return Response('Film was created', 200)
        return Response('Not enough data', 400)


@app.route('/api/1/films/<film_id>', methods=['GET', 'DELETE', 'PUT'])
@jwt_token_required
def handle_film(film_id):
    if request.method == 'GET':
        film = Film.query.get(film_id)
        if not film:
            return Response('Film not exist', 403)
        return Response(json.dumps(film.serialize()), 200)
    if request.method == 'DELETE':
        film = Film.query.get(film_id)
        if not film:
            return Response('Film not exist', 403)
        db.session.delete(film)
        db.session.commit()
        return Response("Film was deleted", 200)
    if request.method == 'PUT':
        update_status = update_film(request, film_id)
        if update_status == 200:
            return Response("Film was updated", 200)
        return Response("Not enough data for update", 400)


@app.route('/api/1/assessment', methods=['POST'])
@jwt_token_required
def make_assessment():
    client_id = request.form.get('client_id', None)
    film_id = request.form.get('film_id', None)
    assessment_value = request.form.get('assessment_value', None)
    if not client_id or not film_id or not assessment_value:
        return Response("Not enough data", 400)

    client = Client.query.get(client_id)
    film = Film.query.get(film_id)
    client.make_assessment(assessment_value, film)
    return Response("Assessment created", 200)


@app.route('/api/1/assessment/<user_id>', methods=['GET'])
@jwt_token_required
def get_assessnent(user_id):
    client = Client.query.get(user_id)
    return Response(json.dumps({'assessment': client.assessments}), 200)


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
        return Response("Not enough data", 400)
    client = Client.query.filter_by(login=login).first()
    if client and client.verify_password(password):
        client.access_token = generate_token(client).decode()
        client.refresh_token = generate_token(client, for_access=False).decode()

        db.session.add(client)
        db.session.commit()
        return Response(
            json.dumps(
                {'access_token': client.access_token,
                 'refresh_token': client.refresh_token}), 200
        )
    else:
        return Response('Client not exist', 403)


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
        return Response("Refreshing success", 200)
    else:
        return Response("Invalid refresh token", 401)
