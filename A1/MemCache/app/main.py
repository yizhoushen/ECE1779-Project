import threading
import time
from collections import OrderedDict
from sys import getsizeof
import random
from datetime import datetime, timedelta

# database
import mysql.connector
from app.config import db_config

# flask
from app import webapp_memcache
from flask import jsonify, request
from flask import json
from flask import render_template

SECONDS_WRITING_2DB_INTERVAL = 5


# database prepare & connect
def connect_to_database():
    return mysql.connector.connect(user=db_config['user'],
                                   password=db_config['password'],
                                   host=db_config['host'],
                                   database=db_config['database'],
                                   auth_plugin='mysql_native_password')


def get_db():
    db = connect_to_database()
    return db


# @webapp.teardown_appcontext
# def teardown_db(exception):
#     db = getattr(g, '_database', None)
#     if db is not None:
#         db.close()


# MemCache class starts here
class PicMemCache(object):

    def __init__(self, memCacheCapacity=None) -> None:
        # get memCacheCapacity from db，but此处没有对数据合法性进行验证
        cnx = get_db()
        cursor = cnx.cursor()
        clear_table_statistics = "truncate table statistics"
        cursor.execute(clear_table_statistics)
        sql_load_capacity = "SELECT Capacity FROM configuration WHERE id = 1"
        cursor.execute(sql_load_capacity)
        # self.memCacheCapacity = memCacheCapacity
        self.memCacheCapacity = cursor.fetchone()[0]

        # Statistical variables
        self.drop_approach = 1
        self.currentMemCache = 0
        self.ItemNum = 0
        self.TotalRequestNum = 0
        self.MissNum = 0
        self.HitNum = 0
        self.GetPicRequestNum = 0

        self.MC = OrderedDict()
        print("memCacheCapacity", self.memCacheCapacity)

    def drop_specific_pic(self, keyID):
        self.TotalRequestNum += 1
        if keyID in self.MC.keys():
            # invalidateKey(key) to drop a specific key.
            self.currentMemCache -= getsizeof(self.MC[keyID])
            self.MC.pop(keyID)
            self.ItemNum -= 1

    def drop_pic(self, approach=0):
        # The default method is Random Replacement
        # Random Replacement
        if approach == 0:
            print("Random Replacement")
            rKey = random.choice(list(self.MC.keys()))
            print('dropped key:{}'.format(rKey))
            self.drop_specific_pic(rKey)

        # Least Recently Use (LRU)
        elif approach == 1:
            print("LRU")
            self.drop_specific_pic(next(iter(self.MC)))

    def put_pic(self, keyID, picString):
        self.TotalRequestNum += 1
        print("put func: ", threading.current_thread().name)
        # This is the process by which the specific image is written to the memcache and cannot be called directly
        if self.memCacheCapacity < getsizeof(picString):
            return "Cache failure! MemCache capacity is too small, even smaller than the image size, please increase the memCache capacity."
        elif self.currentMemCache + getsizeof(picString) <= self.memCacheCapacity:
            # After adding new images, the total MemCache capacity is not exceeded
            self.MC[keyID] = picString
            self.currentMemCache += getsizeof(picString)
            self.ItemNum += 1
            return "Caching success! Images go directly to cache."
        else:
            # After adding new images, the total MemCache capacity is exceeded: you need to discard the images and deposit new ones

            cnx = get_db()
            cursor = cnx.cursor()
            sql_load_replace_policy = "SELECT ReplacePolicy FROM configuration WHERE id = 1"
            cursor.execute(sql_load_replace_policy)
            self.drop_approach = cursor.fetchone()[0]
            print("drop_approach: ", self.drop_approach)

            while self.currentMemCache + getsizeof(picString) > self.memCacheCapacity:
                self.drop_pic(self.drop_approach)
            self.MC[keyID] = picString
            self.currentMemCache += getsizeof(picString)
            self.ItemNum += 1
            # print('Memcache set key {}'.format(keyID))
            return "Caching success! Deleted the previous cached content."

    def get_pic(self, keyID):
        # Functions: 1. Accelerate when you need to see a picture;
        # Functions: 2. Determine whether a picture is in the memcache
        # The only call to write to the memCache
        self.TotalRequestNum += 1
        print("get func: ", threading.current_thread().name)

        self.GetPicRequestNum += 1

        if keyID in self.MC.keys():
            # The case that the image to be called is in the MemCache
            self.MC.move_to_end(key=keyID, last=True)
            self.HitNum += 1
            return self.MC[keyID]
        else:
            # The called image is not in the MemCache
            self.MissNum += 1
            print("MemCache does not have this image")
            return None

    def clear_memcache(self):
        self.MC.clear()

        # All statistics are cleared
        self.currentMemCache = 0
        self.ItemNum = 0
        self.TotalRequestNum = 0
        self.MissNum = 0
        self.HitNum = 0
        self.GetPicRequestNum = 0

    def refreshConfiguration(self):
        self.TotalRequestNum += 1
        cnx = get_db()
        cursor = cnx.cursor()
        sql_reconfig = "SELECT Capacity,ReplacePolicy FROM configuration WHERE id = 1"
        cursor.execute(sql_reconfig)
        result = cursor.fetchone()
        if not result:
            # print('No configuration in the database')
            return 'Database reconfiguration failed! Because there is no configuration in the database.'
        else:
            newMemCacheCapacity = result[0]
            newDropApproach = result[1]

            if newMemCacheCapacity < 0 or newDropApproach not in [0, 1]:
                # Database Compliance Check
                # print('Database configuration is not standardized')
                return 'Database reconfiguration failed! Because the data in the database is invalid.'
            self.drop_approach = newDropApproach
            print("drop_approach: ", self.drop_approach)

            while newMemCacheCapacity < self.currentMemCache:
                self.drop_pic(self.drop_approach)
            self.memCacheCapacity = newMemCacheCapacity
            return 'Database reconfiguration successful!'

    def get_info(self):
        # for test
        print("currentMem: ", self.currentMemCache)
        # print("memCacheCapacity: ", self.memCacheCapacity)
        # print(self.MC)

    def write_statistics_2db(self):
        while True:
            print("statistic report: ", threading.current_thread().name)
            print("CurrentTime", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            cnx = get_db()
            cursor = cnx.cursor()
            query_write2db = ''' INSERT INTO statistics (CurrTime, 
                                                ItemNum, 
                                                CurrentMemCache, 
                                                TotalRequestNum, 
                                                GetPicRequestNum, 
                                                MissRate, 
                                                HitRate)
                        VALUES (%s,%s,%s,%s,%s, %s,%s)
                    '''
            cursor.execute(query_write2db, (datetime.now().strftime("%y-%m-%d %H:%M:%S"),
                                            self.ItemNum,
                                            self.currentMemCache,
                                            self.TotalRequestNum,
                                            self.GetPicRequestNum,
                                            -1 if self.GetPicRequestNum == 0 else self.MissNum / self.GetPicRequestNum,
                                            -1 if self.GetPicRequestNum == 0 else self.HitNum / self.GetPicRequestNum))
            cnx.commit()

            # start_time = (datetime.now() - timedelta(seconds=600)).strftime("%y-%m-%d %H:%M:%S")
            # query_delete =  ''' DELETE FROM statistics WHERE CurrTime < %s '''
            # cursor.execute(query_delete, (start_time,))
            # cnx.commit()

            time.sleep(SECONDS_WRITING_2DB_INTERVAL)


# following for test
memory1 = PicMemCache()
threading.Thread(target=memory1.write_statistics_2db, daemon=True).start()


# for i in range(60):
#     memory1.put_pic(i,"picture1")
#     memory1.get_info()
# memory1.drop_pic(DROP_APPROACH)
# memory1.clear_memcache() # Test success
# memory1.Front_end_upload(4)  # Test success
# memory1.refreshConfiguration(0)  # Test success
# print(memory1.get_pic(8))
# memory1.drop_specific_pic(4)
# memory1.get_info()


@webapp_memcache.route('/put_kv', methods=['POST'])
def put_kv():
    # Write to mamcache
    key = request.form.get('key')
    value = request.form.get('value')
    # Fig 1.(5) PUT
    res_put = memory1.put_pic(keyID=key, picString=value)
    # Fig 1.(6) OK
    if "success" in res_put:
        response = jsonify(success='True',
                           message=res_put)
    else:
        response = jsonify(success='False',
                           message=res_put)
    return response


@webapp_memcache.route('/get', methods=['POST'])
def get():
    #If the image is in memcache, return "Ture+image cache"; if not, return "false+empty"
    key = request.form.get('key')
    # Fig 1.(1) GET
    pic_value = memory1.get_pic(keyID=key)

    if pic_value:
        # OK
        response = jsonify(success='True',
                           content=pic_value)
    else:
        # Fig 1.(2) MISS
        response = jsonify(success='False',
                           content='')
    return response


@webapp_memcache.route('/clear', methods=['POST'])
def clear():
    # clear memcache
    memory1.clear_memcache()
    response = jsonify(success='True')
    return response


@webapp_memcache.route('/invalidateKey', methods=['POST'])
def invalidateKey():
    # 2 places to use this function:
    # 1. from the memcache, according to the key to delete specific images;
    # 2. upload images when used to remove duplicate keyID images of the memcache
    # Yizhou: When you upload an image, just call it, do not care if it is a duplicate keyID

    # Fig 2.(2) invalidateKey
    key = request.form.get('key')
    memory1.drop_specific_pic(keyID=key)
    # Fig 2.(3) OK
    response = jsonify(success='True')
    return response


@webapp_memcache.route('/refreshConfiguration', methods=['POST'])
def refreshConfiguration():
    res = memory1.refreshConfiguration()
    if 'successful' in res:
        # Successfully read the new parameters from the database and changed the parameter configuration
        response = jsonify(success='True')
    else:
        # There is a problem with the data specification (2 cases), read message for the exact reason.
        response = jsonify(success='False',
                           message=res)
    return response


# @webapp_memcache.route('/upload', methods=['POST'])
# def Front_end_upload():
#     key = request.form.get('key')
#     memory1.Front_end_upload(keyID=key)
#     response = jsonify(success='True')
#     return response


@webapp_memcache.route('/', methods=['GET'])
def main():
    return render_template("memcache_view.html", memory1=memory1)
