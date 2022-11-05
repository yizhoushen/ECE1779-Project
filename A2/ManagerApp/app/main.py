from flask import render_template, url_for, request
from app import webapp_manager
from flask import json
from flask import jsonify


@webapp_manager.route('/')
def main():
    return render_template("main.html")


