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
import logging
# A2
import boto3
import cloudwatch
import socket
from botocore.exceptions import ClientError

SECONDS_WRITING_2DB_INTERVAL = 5
response_from_cloudwatch = {}
StorageResolution = 60


# SECONDS_WRITING_2DB_INTERVAL = 5  #for test


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

        ## how to identify each memcache instance?
        # sql_load_instanceID = "SELECT instanceID FROM memcachelist WHERE MemcacheID = %s"
        # cursor.execute(sql_load_instanceID, (MemcacheID,))
        # if not cursor.fetchone()[0]:
        #     self.intance_id = cursor.fetchone()[0]
        # else:
        #     pass

        # Statistical variables
        self.drop_approach = 1
        self.currentMemCache = 0
        self.ItemNum = 0
        self.TotalRequestNum = 0
        self.MissNum = 0
        self.HitNum = 0
        self.GetPicRequestNum = 0

        self.MemcacheID = 0
        self.InstanceID = 'current runing instance id'
        # self.InstanceID = 'string'
        self.PublicIP = '127.0.0.1'

        self.MC = OrderedDict()
        print("memCacheCapacity", self.memCacheCapacity)

    def drop_specific_pic(self, keyID):
        self.TotalRequestNum += 1
        if keyID in self.MC.keys():
            # invalidateKey(key) to drop a specific key.
            self.currentMemCache -= getsizeof(self.MC[keyID])
            self.MC.pop(keyID)
            self.ItemNum -= 1
        # 返回成功与否

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
        # 具体的图片写入memcache过程，不可首次调用
        if self.memCacheCapacity < getsizeof(picString):
            # print("memCache容量过小，甚至小于本张图片大小，请增大memCache，本次缓存失败")
            return "Cache failure! MemCache capacity is too small, even smaller than the image size, please increase the memCache capacity."
        elif self.currentMemCache + getsizeof(picString) <= self.memCacheCapacity:
            # 加入新图片后，没有超过MemCache总容量
            self.MC[keyID] = picString
            self.currentMemCache += getsizeof(picString)
            self.ItemNum += 1
            return "Caching success! Images go directly to cache."
        else:
            # 加入新图片后，超过了MemCache总容量：需要丢掉图片，存入新图片

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
        # 功能：1.需要看图时，加速；2.判断一张图片是否在memcache中
        # 唯一的，调用写入memCache的情况
        self.TotalRequestNum += 1
        print("get func: ", threading.current_thread().name)

        self.GetPicRequestNum += 1

        if keyID in self.MC.keys():
            # 调用的图片就在MemCache
            self.MC.move_to_end(key=keyID, last=True)
            self.HitNum += 1
            return self.MC[keyID]
        else:
            # 调用的图片不在MemCache
            self.MissNum += 1
            print("MemCache无此图片")
            return None

    def clear_memcache(self):
        self.MC.clear()
        # if self.MC == None: 这里需要判断空嘛

        # 所有统计清零
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
            # print('数据库里没配置，拜拜')
            return 'Database reconfiguration failed! Because there is no configuration in the database.'
        else:
            newMemCacheCapacity = result[0]
            newDropApproach = result[1]

            if newMemCacheCapacity < 0 or newDropApproach not in [0, 1]:
                # 数据库合规性检查
                # print('数据库配置不合规范，拜拜')
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

    def update_memcache_info(self, InstanceID, PublicIP, MemcacheID):
        self.MemcacheID = MemcacheID
        self.InstanceID = InstanceID
        self.PublicIP = PublicIP

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

    def send_statistics_2CloudWatch(self):
        while True:
            time.sleep(SECONDS_WRITING_2DB_INTERVAL)
            print("statistic report1: ", threading.current_thread().name)
            print("CurrentTime", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            if self.GetPicRequestNum == 0:
                miss_rate = -1
            else:
                miss_rate = self.MissNum / self.GetPicRequestNum

            print("miss number:", self.MissNum)
            cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')

            global response_from_cloudwatch
            response_from_cloudwatch = cloudwatch.put_metric_data(
                Namespace='statistical_variable_of_one_instance',
                MetricData=[
                    {
                        'MetricName': 'single_ItemNum',
                        'Dimensions': [
                            {
                                'Name': 'instance-id',
                                'Value': self.InstanceID
                            },
                        ],
                        'Value': self.ItemNum,
                        'StorageResolution': StorageResolution,
                    },

                    {
                        'MetricName': 'single_currentMemCache',
                        'Dimensions': [
                            {
                                'Name': 'instance-id',
                                'Value': self.InstanceID
                            },
                        ],
                        'Value': self.currentMemCache,
                        'StorageResolution': StorageResolution,
                    },

                    {
                        'MetricName': 'single_TotalRequestNum',
                        'Dimensions': [
                            {
                                'Name': 'instance-id',
                                'Value': self.InstanceID
                            },
                        ],
                        'Value': self.TotalRequestNum,
                        'StorageResolution': StorageResolution,
                    },

                    {
                        'MetricName': 'single_GetPicRequestNum',
                        'Dimensions': [
                            {
                                'Name': 'instance-id',
                                'Value': self.InstanceID
                            },
                        ],
                        'Value': self.GetPicRequestNum,
                        'StorageResolution': StorageResolution,
                    },

                    {
                        'MetricName': 'single_miss_rate',
                        'Dimensions': [
                            {
                                'Name': 'instance-id',
                                'Value': self.InstanceID
                            },
                        ],
                        'Value': miss_rate,
                        'StorageResolution': StorageResolution,
                    },

                    {
                        'MetricName': 'single_hit_rate',
                        'Dimensions': [
                            {
                                'Name': 'instance-id',
                                'Value': self.InstanceID
                            },
                        ],
                        'Value': -1 if self.GetPicRequestNum == 0 else self.HitNum / self.GetPicRequestNum,
                        'StorageResolution': StorageResolution,
                    },

                    {
                        'MetricName': 'single_miss_num',
                        'Dimensions': [
                            {
                                'Name': 'instance-id',
                                'Value': self.InstanceID
                            },
                        ],
                        'Value': self.MissNum,
                        'StorageResolution': StorageResolution,
                    },

                    {
                        'MetricName': 'singe_hit_num',
                        'Dimensions': [
                            {
                                'Name': 'instance-id',
                                'Value': self.InstanceID
                            },
                        ],
                        'Value': self.HitNum,
                        'StorageResolution': StorageResolution,
                    }
                ]
            )
            print(response_from_cloudwatch)
            # time.sleep(SECONDS_WRITING_2DB_INTERVAL)


memory1 = PicMemCache()
# threading.Thread(target=memory1.write_statistics_2db, daemon=True).start()
threading.Thread(target=memory1.send_statistics_2CloudWatch, daemon=True).start()


# threading.Thread(target=memory1.read_statistics_2CoudWatch, daemon=True).start()


# for i in range(60):
#     memory1.put_pic(i,"picture1")
#     memory1.get_info()
# memory1.drop_pic(DROP_APPROACH)
# memory1.clear_memcache() # 测试正常
# memory1.Front_end_upload(4)  # 测试正常
# memory1.refreshConfiguration(0)  # 测试正常
# print(memory1.get_pic(8))
# memory1.drop_specific_pic(4)
# memory1.get_info()


@webapp_memcache.route('/put_kv', methods=['POST'])
def put_kv():
    # 写入mamcache
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
    # memcache中有该图片时，返回”Ture+图片cache“；没有时，返回”false+空“
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
    # 清除memcache
    memory1.clear_memcache()
    response = jsonify(success='True')
    return response


@webapp_memcache.route('/invalidateKey', methods=['POST'])
def invalidateKey():
    # 2个地方使用本函数：1.从memcache中，根据key删除特定图片；2.upload图片时，用于去掉重复keyID图片的memcache
    # Yizhou你上传图片时，调用就行，不用管是不是重复keyID啥的都不用管

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
        # 成功从数据库读取新参数，并更改了参数配置
        response = jsonify(success='True')
    else:
        # 数据规范有问题（2种情况），没有更改，具体原因见读取message即可。
        response = jsonify(success='False',
                           message=res)
    return response


@webapp_memcache.route('/updateMemcacheInfo', methods=['POST'])
def updateMemcacheInfo():
    MemcacheID = request.form.get('memcache_id')
    InstanceID = request.form.get('instance_id')
    PublicIP = request.form.get('public_ip')
    memory1.update_memcache_info(InstanceID, PublicIP, MemcacheID)
    response = jsonify(success='True')
    return response


# @webapp_memcache.route('/upload', methods=['POST'])
# def Front_end_upload():
#     key = request.form.get('key')
#     memory1.Front_end_upload(keyID=key)
#     response = jsonify(success='True')
#     return response


@webapp_memcache.route('/', methods=['GET'])
def main():
    return render_template("memcache_view.html", memory1=memory1,
                           response_from_cloudwatch=str(response_from_cloudwatch))

@webapp_memcache.route("/testput", methods=['POST'])
def testput():




    try:
        global response_from_cloudwatch
        logging.info("try initiating cloudwatch")
        cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
        logging.info("try submitting data")
        response_from_cloudwatch = cloudwatch.put_metric_data(
            Namespace='statistical_variable_of_one_instance',
            MetricData=[
                {
                    'MetricName': 'single_ItemNum',
                    'Dimensions': [
                        {
                            'Name': 'instance-id',
                            'Value': 'zihe'
                        },
                    ],
                    'Value': 111,
                    'StorageResolution': StorageResolution,
                    'Unit': 'Count'
                },

                {
                    'MetricName': 'single_currentMemCache',
                    'Dimensions': [
                        {
                            'Name': 'instance-id',
                            'Value': 'zihe'
                        },
                    ],
                    'Value': 222,
                    'StorageResolution': StorageResolution,
                    'Unit': 'Count'
                },

                {
                    'MetricName': 'single_TotalRequestNum',
                    'Dimensions': [
                        {
                            'Name': 'instance-id',
                            'Value': 'zihe'
                        },
                    ],
                    'Value': 333,
                    'StorageResolution': StorageResolution,
                    'Unit': 'Count'
                },

                {
                    'MetricName': 'single_GetPicRequestNum',
                    'Dimensions': [
                        {
                            'Name': 'instance-id',
                            'Value': 'zihe'
                        },
                    ],
                    'Value': 444,
                    'StorageResolution': StorageResolution,
                    'Unit': 'Count'
                },

                {
                    'MetricName': 'single_miss_rate',
                    'Dimensions': [
                        {
                            'Name': 'instance-id',
                            'Value': 'zihe'
                        },
                    ],
                    'Value': 555,
                    'StorageResolution': StorageResolution,
                    'Unit': 'Count'
                },

                {
                    'MetricName': 'single_hit_rate',
                    'Dimensions': [
                        {
                            'Name': 'instance-id',
                            'Value': 'zihe'
                        },
                    ],
                    'Value': 666,
                    'StorageResolution': StorageResolution,
                    'Unit': 'Count'
                },

                {
                    'MetricName': 'single_miss_num',
                    'Dimensions': [
                        {
                            'Name': 'instance-id',
                            'Value': 'zihe'
                        },
                    ],
                    'Value': 777,
                    'StorageResolution': StorageResolution,
                    'Unit': 'Count'
                },

                {
                    'MetricName': 'singe_hit_num',
                    'Dimensions': [
                        {
                            'Name': 'instance-id',
                            'Value': 'zihe'
                        },
                    ],
                    'Value': 888,
                    'StorageResolution': StorageResolution,
                    'Unit': 'Count'
                }
            ]
        )
    except Exception as e:
        logging.error(e)
        return jsonify({"success": False})
    logging.info("successfully!")
    return jsonify({"success": True})
    # print(response_from_cloudwatch)