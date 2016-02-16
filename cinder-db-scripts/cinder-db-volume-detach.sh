#!/bin/bash
user_name="root"
password="test123"
volume_id=$1

if [ -z $1 ];
then
    echo "Need to pass volume_id as first argument"
    exit
fi

mysql -u $user_name -p$password -Bse " use cinder;  \
        update volumes set attach_status='detached',status='available' \
        WHERE id='$volume_id';"
