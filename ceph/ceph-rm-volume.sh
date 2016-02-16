#!/bin/bash
user="cinder"
conf="/etc/ceph/ceph.conf"
pool="sbs"
volume_id="volume_id"

if [ -z $1 ];
then
    echo "Need to pass volume_id as first argument"
    exit
fi

rbd --user $user --conf $conf -p $pool rm "volume-$volume_id"
