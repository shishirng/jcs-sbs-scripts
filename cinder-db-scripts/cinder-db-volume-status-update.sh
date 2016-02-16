#!/bin/bash
user_name="root"
password="test123"
volume_id=$1
vol_status=$2

if [ -z $1 ];
then
    echo "Need to pass volume_id as first argument"
    exit
fi

if [ -z $2 ];
then
    echo "Need to pass status as the second argument"
    exit
fi

mysql -u $user_name -p$password -Bse " use cinder;  \
        update volumes set status='$vol_status'\
        WHERE id='$volume_id';"
