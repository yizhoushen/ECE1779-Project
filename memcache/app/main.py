
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

@webapp.route('/image_form', methods=['GET'])
def image_form():
    return render_template("image_form.html", title="Select Image Key")

@webapp.route('/image_display', methods=['POST'])
def image_display():
    # implement /image_display
    if 'image_key' not in request.form:
        return "Need a image key"

    image_key = request.form.get('image_key')

    if image_key == '':
        return "Need a image key"

    cnx = get_db()
    cursor = cnx.cursor()

    query = ''' SELECT ImagePath FROM imagelist
                WHERE ImageID = %s'''

    cursor.execute(query, (image_key,))
    row = cursor.fetchone()
    
    if row == None:
        return "No such image"

    # image_path = os.path.join('static/images', row[1])
    image_path = row[0]

    return render_template("image_display.html", title="Image Display", image_path=image_path)


@webapp.route('/all_keys', methods=['GET'])
def all_keys():
    cnx = get_db()

    cursor = cnx.cursor()

    query = "SELECT * FROM imagelist"

    cursor.execute(query)

    return render_template("keylist.html", title="ImageID List", cursor=cursor)


@webapp.route('/config_mem_cache', methods=['GET'])
def config_mem_cache():
    # implement /config_mem_cache
    return render_template("main.html")

@webapp.route('/statistics', methods=['GET'])
def statistics():
    # implement /statistics
    return render_template("main.html")