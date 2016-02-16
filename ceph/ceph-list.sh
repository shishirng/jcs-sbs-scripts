#!/bin/bash
user="cinder"
conf="/etc/ceph/ceph.conf"
pool="sbs"

rbd --user $user --conf $conf -p $pool ls
