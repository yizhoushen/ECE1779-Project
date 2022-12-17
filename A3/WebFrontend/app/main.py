import app
from flask import render_template, redirect, url_for, request, g
from app import webapp, memcache
from flask import json
from datetime import datetime, timedelta

import mysql.connector
from app.config import db_config, s3_bucket, aws_access_key, aws_secret_key
import sys

import time

import requests
import base64

import boto3

# os.chdir(os.path.abspath("./A1/WebFrontend"))

images_tag = {}
username = 'username'

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

# @webapp.route('/',methods=['GET'])
@webapp.route('/main',methods=['GET'])
def main():
    print("getting main page! userid: {}".format(app.userid))
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass
    return render_template("main.html")


@webapp.route('/all_keys', methods=['GET'])
def all_keys():
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass
    cnx = get_db()
    cursor = cnx.cursor()
    query = "SELECT * FROM imagelist"
    cursor.execute(query)
    return render_template("keylist.html", title="ImageID List", cursor=cursor)


@webapp.route('/statistics', methods=['GET'])
def statistics():
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass
    cnx = get_db()
    cursor = cnx.cursor()
    query = "SELECT * FROM statistics"
    cursor.execute(query)

    start_time = datetime.now() - timedelta(minutes=10)
    return render_template("statistics.html", title="Memory Cache Statistics", cursor=cursor, start_time=start_time)


# @webapp.route('/api_test', methods=['POST', 'GET'])
# def test_api():
#     response = requests.post("http://127.0.0.1:5000/api/list_keys", timeout=5)
#     print("Response from api/key_list: {}".format(response.text))
#     return "okkkk"


