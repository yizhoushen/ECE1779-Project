
from flask import render_template, url_for, request, g
from app import webapp, memcache
from flask import json

import mysql.connector
from app.config import db_config
import sys

def connect_to_database():
    return mysql.connector.connect(user=db_config['user'],
                                   password=db_config['password'],
                                   host=db_config['host'],
                                   database=db_config['database'])

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = connect_to_database()
    return db

@webapp.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# @webapp.route('/')
@webapp.route('/',methods=['GET'])
@webapp.route('/main',methods=['GET'])
def main():
    return render_template("main.html")

@webapp.route('/get',methods=['POST'])
def get():
    key = request.form.get('key')

    if key in memcache:
        value = memcache[key]
        response = webapp.response_class(
            response=json.dumps(value),
            status=200,
            mimetype='application/json'
        )
    else:
        response = webapp.response_class(
            response=json.dumps("Unknown key"),
            status=400,
            mimetype='application/json'
        )

    return response

@webapp.route('/put',methods=['POST'])
def put():
    key = request.form.get('key')
    value = request.form.get('value')
    memcache[key] = value

    response = webapp.response_class(
        response=json.dumps("OK"),
        status=200,
        mimetype='application/json'
    )

    return response

########################################################

@webapp.route('/upload', methods=['GET'])
def upload():
    # implement /upload
    return render_template("main.html")

@webapp.route('/show_image', methods=['GET'])
def show_image():
    # implement /show_image
    return render_template("main.html")


@webapp.route('/all_keys', methods=['GET'])
def all_keys():
    cnx = get_db()

    cursor = cnx.cursor()

    query = "SELECT * FROM imagelist"

    cursor.execute(query)

    return render_template("keylist.html",title="ImageID List", cursor=cursor)


@webapp.route('/config_mem_cache', methods=['GET'])
def config_mem_cache():
    # implement /config_mem_cache
    return render_template("main.html")

@webapp.route('/statistics', methods=['GET'])
def statistics():
    # implement /statistics
    return render_template("main.html")