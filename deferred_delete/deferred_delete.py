from datetime import datetime
import mysql.connector
import sys
import rados
import rbd
import pdb
from oslo_utils import encodeutils
import logging as log
import os

log.basicConfig(filename='deferred_delete.log',level=log.DEBUG)

def check_pending_backups(cxn, volume_id):
    cursor = cxn.cursor()
    query = "SELECT id from backups WHERE volume_id='{id}' AND status='creating'"
    active_query = query.format(id=volume_id)
    log.debug("%s", active_query)
    cursor.execute(active_query)
    ids = cursor.fetchall()
    ret = 0
    if id in ids:
        ret = 1
    #cursor.close()
    return ret

def delete_backups(image, id, cxn):
    # check db for any snapshot in 'creating' state
    ret = check_pending_backups(cxn,id)
    if ret != 0:
        log.error("Volume %s has snapshot in creating state", id)
        raise Exception()

    # delete snaps if no snapshot is in creating state
    snap_list = image.list_snaps()
    for snap in snap_list:
        try:
            snap_name = encodeutils.safe_encode(snap['name'])
	    log.info("removing snap %s for volume %s", snap_name, id)
            image.remove_snap(snap_name)
        except self.rbd.ImageNotFound:
            log.info("Snapshot %s already deleted for volume %s", snap_name, id)
            pass
        except Exception as e:
            log.error("failed to delete snap %s for volume %s", (snap['name'], id))
            raise e

def mark_cleaned(cxn, id):
	cursor = cxn.cursor()
        log.info("updating db for volume id %s", id)
        query = "update volumes set cleaned=True where id='{id}'"
        active_query = query.format(id=id)
	cursor.execute(active_query)
	cxn.commit()
	log.debug("%s",active_query)


def delete_volumes(cleaner_name, ioctx, cxn, id):
    # try to claim ownership
    query = "update volumes set cleaner=IF(cleaner IS NULL,'{worker}', cleaner) where id='{id}'"
    active_query = query.format(worker=cleaner_name, id=id)
    log.debug("%s", active_query)
    cursor = cxn.cursor()
    cursor.execute(active_query)
    cxn.commit()

    query1 = "select cleaner from volumes where id='{id}'"
    active_query1 = query1.format(id=id)
    log.debug("%s", active_query1)
    cursor.execute(active_query1)
    for cleaner in cursor:
	log.debug("volume %s owned by cleaner:%s", id, cleaner[0])
        if cleaner[0] != cleaner_name:
            log.info("Not cleaningvolume %s as it is owned by %s", (id, cleaner))
            return

    log.info("Deleting volume %s", id)
    volume_name = encodeutils.safe_encode("volume-%s" % id)
    rbd_inst = rbd.RBD()
    try:
        image = rbd.Image(ioctx, volume_name, read_only=False)
    except rbd.ImageNotFound:
	log.info("Volume %s already deleted from ceph", id)
	mark_cleaned(cxn, id)
        return	

    try:
        delete_backups(image, id, cxn)
        image.close()
        log.info("removing rbd image %s", volume_name)
        rbd_inst.remove(ioctx, volume_name)
	mark_cleaned(cxn, id)

    except Exception as e:
        image.close()
        log.error("Failed to delete volume %s",id)
        raise e

def connect_to_rados(userid, pool):
    client = rados.Rados(rados_id=userid, conffile="/etc/ceph/ceph.conf")
    try:
        client.connect()
        io_ctx = client.open_ioctx(pool)
        return client, io_ctx
    except rados.Error as e:
        client.shutdown()
        log.error("Failed to connect to cluster")
        raise e

userid = encodeutils.safe_encode("cinder")
pool = encodeutils.safe_encode("sbs")

client, ioctx = connect_to_rados(userid, pool)

db_host = '10.140.12.203'
cnx = mysql.connector.connect(host= db_host, user='root',password='test123', database='cinder')
cursor = cnx.cursor(buffered=True)


worker = 0
hostname = os.uname()[1]
cleaner_name = hostname + '-' + str(worker)
log.info("%s: Starting cleaner: %s", str(datetime.now()), cleaner_name)

query = ("SELECT id FROM volumes WHERE cleaned=False AND deleted=1 AND (cleaner IS NULL OR cleaner='{cleaner}')")
active_query = query.format(cleaner=cleaner_name)
cursor.execute(active_query)
vols = cursor.fetchall()
#pdb.set_trace()
for id in vols:
    log.info('Deleting %s', id[0])
    delete_volumes(cleaner_name, ioctx, cnx, id[0])
cursor.close()
cnx.close()

ioctx.close()
client.shutdown()
