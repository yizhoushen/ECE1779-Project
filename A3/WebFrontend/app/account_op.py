import app
from flask import render_template, redirect, url_for, request, g
from app import webapp
from app.config import db_config, s3_bucket, aws_access_key, aws_secret_key
import requests
import time
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb', 
                          region_name='us-east-1',
                          aws_access_key_id=aws_access_key,
                          aws_secret_access_key=aws_secret_key)


@webapp.route('/')
@webapp.route('/signup')
def index():
    return render_template('accounts/signup.html')


@webapp.route('/signup_complete', methods=['post'])
def signup_complete():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']

    if email == '':
        return "Email cannot be empty!"
    if name == '':
        return "Name cannot be empty!"
    if password == '':
        return "Password cannot be empty!"
    
    profile = {
        'NickName': name,
        'ProfilePic': '',
        'Biography': '',
        'Mood': ''
    }

    table = dynamodb.Table('UserTable')
    
    table.put_item(
        Item={
            'email': email,
            'password': password,
            'profile': profile
        }
    )
    msg = "Registration Complete. Please Login to your account !"

    return redirect(url_for('login'))

@webapp.route('/login')
def login():    
    return render_template('accounts/login.html')


@webapp.route('/check',methods = ['post'])
def check():       
    email = request.form['email']
    password = request.form['password']
    
    table = dynamodb.Table('UserTable')
    response = table.query(
            KeyConditionExpression=Key('email').eq(email)
    )
    items = response['Items']
    print("items: {}".format(items))
    if len(items) == 0:
        return render_template("accounts/login.html", msg="No such email" )
    name = items[0]['profile']['NickName']
    print(items[0]['password'])
    
    if password == items[0]['password']:
        # global userid
        app.userid = email
        print("login! userid: {}".format(app.userid))
        return redirect(url_for('main'))
    else:
        return render_template("accounts/login.html", msg="Wrong password" )

# @webapp.route('/home')
# def home():
#     return render_template('home.html')