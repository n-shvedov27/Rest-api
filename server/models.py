from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import json

from .wsgi import app

db = SQLAlchemy(app)


class Client(UserMixin, db.Model):
    def __init__(self, login: str, email: str, password: str):
        self.login = login
        self.email = email
        self.password_hash = generate_password_hash(password)
        self.registration_date = datetime.datetime.now()

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(128))
    email = db.Column(db.String(120), unique=True)
    registration_date = db.Column(db.DateTime)
    assessments = db.relationship('Assessment', back_populates="client")
    access_token = db.Column(db.String(500))
    refresh_token = db.Column(db.String(500))

    def serialize(self):
        return json.dumps({
            'id': self.id,
            'login': self.login,
            'email': self.email,
            'registration_date': self.registration_date,
            'assessments': [assessment.serialize() for assessment in self.assessments]
        })

    def make_assessment(self, assessment_value: int, film: 'Film'):
        new_assessment = None
        for assessment in self.assessments:
            if assessment.film_id == film.id:
                new_assessment = assessment

        if new_assessment:
            new_assessment.assessment_value = assessment_value
            self.assessments.append(new_assessment)
            film.assessments.append(new_assessment)
            db.session.add(new_assessment)
            db.session.commit()
        else:
            new_assessment = Assessment(assessment_value, self.id, film.id)
            film.assessments.append(new_assessment)
            self.assessments.appenf(new_assessment)
            db.session.add(new_assessment)
            db.session.commit()

    @property
    def password(self):
        raise AttributeError('Password is not readable')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)


class Film(db.Model):
    def __init__(self, film_name: str, creation_year: str, creation_country: str):
        self.film_name = film_name
        self.creation_year = creation_year
        self.creation_country = creation_country

    id = db.Column(db.Integer, primary_key=True)
    film_name = db.Column(db.String(120), unique=True)
    creation_year = db.Column(db.Integer)
    creation_country = db.Column(db.String)
    assessments = db.relationship('Assessment', back_populates="film")

    def serialize(self):
        return json.dumps({
            'id': self.id,
            'film_name': self.film_name,
            'creation_year': self.creation_year,
            'creation_country': self.creation_country,
            'assessments': [assessment.serialize() for assessment in self.assessments]
        })


class Assessment(db.Model):
    def __init__(self, assessment_value: int, client_id: int, film_id: int):
        self.assessment_value = assessment_value
        self.client_id = client_id
        self.film_id = film_id

    id = db.Column(db.Integer, primary_key=True)
    assessment_value = db.Column(db.Integer)

    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))
    client = db.relationship('Client', back_populates='assessments')

    film_id = db.Column(db.Integer, db.ForeignKey('film.id'))
    film = db.relationship('Film', back_populates='assessments')

    def serialize(self):
        return json.dumps({
            'id': self.id,
            'film_name': self.film.film_name,
            'login': self.client.login,
            'assessment_value': self.assessment_value
        })


db.create_all()
