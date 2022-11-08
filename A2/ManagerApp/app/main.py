from flask import render_template, url_for, request
from app import webapp_manager
from flask import json
from flask import jsonify
import requests
import mysql.connector
from app.config import db_config


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

@webapp_manager.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@webapp_manager.route('/', methods=['GET'])
@webapp_manager.route('/main', methods=['GET'])
def main():
    return render_template("main.html")


@webapp_manager.route('/config_form', methods=['GET'])
def config_form():
    return render_template("config_form.html", title="Configure Memory Cache")

@webapp_manager.route('/config_mem_cache', methods=['POST'])
def config_mem_cache():
    if 'cache_clear' not in request.form and 'cache_configure' in request.form:
        if 'memcache_size' not in request.form:
            return "Missing MemCache size"
        
        if 'memcache_policy' not in request.form:
            return "Missing MemCache Replacement Policy"
        
        memcache_szie = request.form.get('memcache_size')
        memcache_policy = request.form.get('memcache_policy')

        if memcache_szie == '':
            return 'MemCache size is empty'
        if memcache_policy == '':
            return 'MemCache Replacement Policy is empty'
        if memcache_policy != '0' and memcache_policy != '1':
            return 'Invalid Replacement Policy'

        cnx = get_db()
        cursor = cnx.cursor()

        query = ''' UPDATE configuration
                    SET Capacity = %s,
                        ReplacePolicy = %s
                    WHERE id = 1'''

        cursor.execute(query, (memcache_szie, int(memcache_policy)))
        cnx.commit()
        
        response = requests.post("http://127.0.0.1:5001/refreshConfiguration", timeout=5)
        res_json = response.json()
        if res_json['success'] == 'True':
            return "Cache configuration is successful"
        elif res_json['success'] == 'False':
            return "Cache configuration failed!"
        else:
            return "Failed to get repsonse from memcache/clear"

        return "Success"
    elif 'cache_clear' in request.form and 'cache_configure' not in request.form:
        response = requests.post("http://127.0.0.1:5001/clear", timeout=5)
        res_json = response.json()
        if res_json['success'] == 'True':
            return "Cache Cleared"
        else:
            return "Failed to get repsonse from memcache/clear"
    else:
        return "Invalid! Please choose cache configure or cache clear"


# @webapp_manager.route('/statistics', methods=['GET'])
# def statistics():
#     cnx = get_db()
#     cursor = cnx.cursor()
#     query = "SELECT * FROM statistics"
#     cursor.execute(query)

#     start_time = datetime.now() - timedelta(minutes=10)
#     return render_template("statistics.html", title="Memory Cache Statistics", cursor=cursor, start_time=start_time)

