import boto
import boto.s3.connection
#from boto.s3.key import Key
import os
import subprocess

import pdb
import pdb
access_key = ''
secret_key = ''
host = 'dss.ind-west-1.staging.jiocloudservices.com'
bucket_name = ''

conn = boto.connect_s3(host=host,aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                       is_secure=True,
                       calling_format = boto.s3.connection.OrdinaryCallingFormat(),)

#pdb.set_trace()

backup_bucket = None
bucket = conn.get_bucket(bucket_name)
if bucket != None:
    print bucket
else:
    conn.create_bucket(bucket_name)

keys = bucket.list()

for key in keys:
    print "%s %d" (key.name, key.size)
