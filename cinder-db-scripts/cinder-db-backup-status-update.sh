#!/bin/bash
user_name="root"
password="test123"
backup_id=$1
backup_status=$2

if [ -z $1 ];
then
    echo "Need to pass backup_id as first argument"
    exit
fi

if [ -z $2 ];
then
    echo "Need to pass status as the second argument"
    exit
fi

mysql -u $user_name -p$password -Bse " use cinder;  \
        update backupss set status='$bakcup_status'\
        WHERE id='$backup_id';"
