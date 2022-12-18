import app
from flask import render_template, redirect, url_for, request, g
from app import webapp, memcache
from flask import json
from datetime import datetime, timedelta

import mysql.connector
from app.config import db_config, s3_bucket, aws_access_key, aws_secret_key
import sys

import time
import os

import requests
import base64

import boto3
from boto3.dynamodb.conditions import Key

from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
import pandas as pd

# os.chdir(os.path.abspath("./A1/WebFrontend"))

images_tag = {}
# username = 'username'

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

def query_user_tag():
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table('Images')

    response = table.query(
        KeyConditionExpression=Key('user_id').eq(app.userid),
        ProjectionExpression="user_id, labels"
    )
    print(response)
    records = []
    for i in response['Items']:
        for single_label in i['labels']:
            records.append(single_label)
    records = list(set(records))
    return records

def get_wordcloud_pic():
    comment_words = ''
    stopwords = set(STOPWORDS)

    # process comment_words
    tag_records = query_user_tag()
    for tag in tag_records:
        comment_words += tag + " "

    print("comment_words: {}".format(comment_words))

    wordcloud = WordCloud(width = 800, height = 800,
				background_color ='white',
				stopwords = stopwords,
				min_font_size = 10).generate(comment_words)

    # plot the WordCloud image					
    plt.figure(figsize = (8, 8), facecolor = None)
    plt.imshow(wordcloud)
    plt.axis("off")
    plt.tight_layout(pad = 0)

    # plt.show()
    wc_save_path = os.path.join("./WebFrontend/app/static/images", "wcgraph.png")
    print("save path: {}".format(wc_save_path))

    plt.savefig(wc_save_path)

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
    nickname = app.username
    return render_template("main.html", nickname=nickname)


@webapp.route('/all_keys', methods=['GET'])
def all_keys():
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass
    # cnx = get_db()
    # cursor = cnx.cursor()
    # query = "SELECT * FROM imagelist"
    # cursor.execute(query)
    # return render_template("keylist.html", title="ImageID List", cursor=cursor)
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table('Images')

    response = table.query(
        KeyConditionExpression=Key('user_id').eq(app.userid),
        ProjectionExpression="user_id, image_key, pic_s3_loc"
    )
    print("response table query: {}".format(response))
    imagelist = []
    for i in response['Items']:
        imagelist.append([i['image_key'], i['pic_s3_loc']])
    print("imagelist: {}".format(imagelist))
    return render_template("keylist.html", title="ImageID List", imagelist=imagelist)


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

@webapp.route('/profile', methods=['GET'])
def profile():
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass
    nickname = app.username
    return render_template("profile.html", title="Profile", nickname=nickname)

@webapp.route('/wordcloud', methods=['GET', 'POST'])
def get_wordcloud():
    if app.userid == None:
        return "Access Denied! Please Login!"
    else:
        pass
    
    get_wordcloud_pic()
    # return "success"
    image_path = os.path.join("./static/images", "wcgraph.png")
    print("image_path: {}".format(image_path))
    return render_template("wordcloud.html", image_path=image_path)

# @webapp.route('/api_test', methods=['POST', 'GET'])
# def test_api():
#     response = requests.post("http://127.0.0.1:5000/api/list_keys", timeout=5)
#     print("Response from api/key_list: {}".format(response.text))
#     return "okkkk"


