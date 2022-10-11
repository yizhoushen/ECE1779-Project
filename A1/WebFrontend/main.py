
from flask import render_template, url_for, request, g
from WebFrontend import webapp, memcache
from flask import json

import mysql.connector
from WebFrontend.config import db_config
import sys

import tempfile
import os

# os.chdir(os.path.abspath("./A1/WebFrontend"))

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

@webapp.route('/',methods=['GET'])
@webapp.route('/main',methods=['GET'])
def main():
    return render_template("main.html")

@webapp.route('/upload_form', methods=['GET'])
def upload_form():
    return render_template("upload_form.html", title="Upload Image")

@webapp.route('/image_upload', methods=['POST'])
def image_upload():
    if 'uploaded_key' not in request.form:
        return "Missing image key"
    
    if 'uploaded_image' not in request.files:
        return "Missing uploaded image"
    
    new_key = request.form.get('uploaded_key')
    new_image = request.files['uploaded_image']

    if new_key == '':
        return 'Image key is empty'
    if new_image.filename == '':
        return 'Missing file name'
    
    ##################################
    # todo: invilidate memcache
    
    s = new_image.filename.split(".")
    file_extension = s[len(s)-1]
    
    # for some reason only the images in '.../ECE1779-Project/A1/WebFrontend/static' folder can be rendered
    # images from other folders got 'GET <other_directory> HTTP/1.1 404' error
    # possible solution: need to manually define static file directory
    # https://stackoverflow.com/questions/67698211/getting-get-static-css-base-css-http-1-1-404-1795-error-for-static-files
    
    temp_path = os.path.join("./static/images", "{}.{}".format(new_key, file_extension))
    dbimage_path = temp_path.replace("\\", "/")

    cnx = get_db()
    cursor = cnx.cursor()

    query_overwrite = '''   INSERT INTO imagelist(ImageID, ImagePath)
                            VALUES(%s, %s) as newimage
                            ON DUPLICATE KEY UPDATE ImagePath=newimage.ImagePath'''

    cursor.execute(query_overwrite, (new_key, dbimage_path))
    cnx.commit()

    # Assume the current directory is .../ECE1779-Project
    new_path = os.path.join(os.path.abspath("./A1/WebFrontend"), dbimage_path)
    save_path = new_path.replace("\\", "/")
    new_image.save(save_path)
    return "Success"

    #========== initial apporach

    # temp_path = os.path.join("./static/images", new_image.filename)
    # dbimage_path = temp_path.replace("\\", "/")

    # cnx = get_db()
    # cursor = cnx.cursor()

    # query_check = '''   SELECT ImagePath FROM imagelist
    #                     WHERE ImageID = %s'''

    # query_insert = '''  INSERT INTO imagelist(ImageID, ImagePath)
    #                     VALUES(%s, %s) as newimage'''

    # query_update = '''  UPDATE imagelist
    #                     SET ImagePath = %s
    #                     WHERE ImageID = %s'''

    # query_overwrite = '''   INSERT INTO imagelist(ImageID, ImagePath)
    #                         VALUES(%s, %s) as newimage
    #                         ON DUPLICATE KEY UPDATE ImagePath=newimage.ImagePath'''

    # cursor.execute(query_check, (new_key,))
    # row = cursor.fetchone()
    # if row == None:
    #     cursor.execute(query_insert, (new_key, dbimage_path,))
    #     cnx.commit()
    # else:
    #     old_image_path = row[0]
    #     delete_path = os.path.join("C:/Users/Harry/MyDocs/UofT/ECE1779/ECE1779-Project/A1/WebFrontend", old_image_path)
    #     os.remove(delete_path)
    #     cursor.execute(query_update, (dbimage_path, new_key,))
    #     cnx.commit()

    # new_path = os.path.join("C:/Users/Harry/MyDocs/UofT/ECE1779/ECE1779-Project/A1/WebFrontend", dbimage_path)
    # save_path = new_path.replace("\\", "/")
    # new_image.save(save_path)
    # return "Success"

@webapp.route('/display_form', methods=['GET'])
def display_form():
    return render_template("display_form.html", title="Select Image Key")

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

    # image_path = os.path.join('static/images', row[0])
    image_path = row[0]

    return render_template("image_display.html", title="Image Display", image_path=image_path)


@webapp.route('/all_keys', methods=['GET'])
def all_keys():
    cnx = get_db()

    cursor = cnx.cursor()

    query = "SELECT * FROM imagelist"

    cursor.execute(query)

    return render_template("keylist.html", title="ImageID List", cursor=cursor)


@webapp.route('/config_form', methods=['GET'])
def config_form():
    return render_template("config_form.html", title="Configure Memory Cache")

@webapp.route('/config_mem_cache', methods=['POST'])
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
        if memcache_policy != 0 or memcache_policy != 1:
            return 'Invalid Replacement Policy'

        cnx = get_db()
        cursor = cnx.cursor()

        query = ''' UPDATE configuration
                    SET Capacity = %s,
                        ReplacePolicy = %s
                    WHERE id = 1'''

        cursor.execute(query, (memcache_szie, memcache_policy))
        cnx.commit()
        
        return "Success"
    elif 'cache_clear' in request.form and 'cache_configure' not in request.form:
        ### todo: Send some JSON request to memcache instance
        return "Cache Cleared"
    else:
        return "Invalid! Please choose cache configure or cache clear"


@webapp.route('/statistics', methods=['GET'])
def statistics():
    cnx = get_db()

    cursor = cnx.cursor()

    query = "SELECT * FROM statistics"

    cursor.execute(query)

    return render_template("statistics.html", title="Memory Cache Statistics", cursor=cursor)

@webapp.route('/testpath', methods=['GET'])
def testpath():
    temp_path = os.path.abspath("./temp_path")
    return temp_path