import boto
import boto.s3.connection
#from boto.s3.key import Key
import os
import subprocess

import pdb
access_key = ''
secret_key = ''
host = 'dss.ind-west-1.staging.jiocloudservices.com'
#host = '10.140.214.250'
bucket_name = ''
backup_id = ""

conn = boto.connect_s3(host=host,aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                       is_secure=True,
                       calling_format = boto.s3.connection.OrdinaryCallingFormat(),)
#pdb.set_trace()

backup_bucket = None
bucket = conn.get_bucket(bucket_name)
if bucket != None:
    print bucket
else:
    keys = bucket.list()

for key in keys:
    print "deleting %s" % key.name
    bucket.delete_key(key.name)
