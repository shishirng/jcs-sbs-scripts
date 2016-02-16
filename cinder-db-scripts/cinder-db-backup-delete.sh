#!/bin/bash
user_name="root"
password="test123"
backup_id=$1

if [ -z $1 ];
then
    echo "Need to pass backup_id as first argument"
    exit
fi

mysql -u $user_name -p$password -Bse " use cinder;  \
        update backups set deleted=1,status='deleted',deleted_at=now(),updated_at=now() \
        where deleted=0 and id='$backup_id';"
