from flask import render_template, url_for, request
from app import webapp_autoscaler
from flask import json
from flask import jsonify


@webapp_autoscaler.route('/')
def main():
    return render_template("main.html")


