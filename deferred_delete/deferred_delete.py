from datetime import datetime
import mysql.connector
import sys
import rados
import rbd
import pdb
from oslo_utils import encodeutils
import logging as log
import os
from multiprocessing import Pool
import time
import ConfigParser

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

def rbd_delete(id, ioctx, cxn):
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

def delete_volumes(cleaner_name, ioctx, cxn, id):
    # try to claim ownership
    query = "update volumes set cleaner=IF(cleaner IS NULL,'{worker}', cleaner),updated_at=NOW() where id='{id}'"
    active_query = query.format(worker=cleaner_name, id=id)
    log.debug("%s", active_query)
    cursor = cxn.cursor()
    cursor.execute(active_query)
    updated = cursor.rowcount
    log.debug("updated %d rows", updated)
    if updated <= 0:
        log.info("Not cleaning volume %s as it is not owned by %s", (id, cleaner))
	return
    cxn.commit()
    rbd_delete(id, ioctx, cxn)

def delete_stale_volumes(cleaner_name, ioctx, cxn, id):
    global retry_interval
    # try to claim ownership
    query = "update volumes set cleaner='{worker}',updated_at=NOW() where id='{id}' AND updated_at < DATE_SUB(NOW(), INTERVAL {interval} hour)"
    active_query = query.format(worker=cleaner_name, id=id, interval=retry_interval)
    log.debug("%s", active_query)
    cursor = cxn.cursor()
    cursor.execute(active_query)
    updated = cursor.rowcount
    log.debug("updated %d rows", updated)
    if updated <= 0:
        log.info("Not cleaning volume %s as it is not owned by %s", (id, cleaner))
	return
    cxn.commit()
    rbd_delete(id, ioctx, cxn)

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

def worker_start(cleaner, ioctx, cnx, cursor):
	global retry_interval
	global vol_type

	log.info("%s: Starting cleaner: %s", str(datetime.now()), cleaner)
	#query = ("SELECT id FROM volumes WHERE cleaned=False AND deleted=1")
	query = ("SELECT id FROM volumes WHERE cleaned=False AND deleted=1 AND cleaner IS NULL AND volume_type_id={vol_type}")
	active_query = query.format(vol_type=vol_type)
	cursor.execute(active_query)
	vols = cursor.fetchall()

	for id in vols:
	    log.info('Deleting %s', id[0])
	    delete_volumes(cleaner, ioctx, cnx, id[0])
	#cursor.close()
	log.info("%s: cleaner:%s going to sleep", str(datetime.now()), cleaner)

	#delete volumes which might have failed
	query = ("SELECT id FROM volumes WHERE cleaned=False AND deleted=1 AND (updated_at < DATE_SUB(NOW(), INTERVAL {interval} HOUR)) AND volume_type_id={vol_type}")
	active_query = query.format(interval = retry_interval, vol_type=vol_type)
	cursor.execute(query)
	vols_stale = cursor.fetchall()

	for id in vols_stale:
            log.info('Deleting %s', id[0])
	    delete_stale_volumes(cleaner, ioctx, cnx, id[0])

	cursor.close()
	
def workerd(cleaner):
        global SLEEPTIME
        global userid
        global pool
	global db_host
	global db_user
	global db_pswd
	global db_database

	log_filename = "/var/log/cinder/" + "deferred_delete-" + cleaner + ".log"
	log.basicConfig(filename=log_filename,level=log.DEBUG)
        while True:
		client, ioctx = connect_to_rados(userid, pool)
		cnx = mysql.connector.connect(host= db_host, user = db_user ,password = db_pswd, database = db_database)
		cursor = cnx.cursor(buffered=True)
		worker_start(cleaner, ioctx, cnx,cursor)
		cnx.close()
		ioctx.close()
		client.shutdown()
		time.sleep(SLEEPTIME)


##globals##
userid = encodeutils.safe_encode("cinder")
pool = encodeutils.safe_encode("sbs")
vol_type = 1
config = ConfigParser.ConfigParser()
config.read("/etc/cinder/deferred_delete.conf")

db_host = config.get('client', 'db_host')
WORKERS = int(config.get('client', 'workers'))
SLEEPTIME = int(config.get('client', 'interval'))
db_user = config.get('client', 'db_user')
db_pswd = config.get('client', 'db_password')
db_database = config.get('client', 'database')
vol_type = config.get('client', 'volume_type')
retry_interval = config.get('client', 'retry_interval')

if vol_type != 'ms1':
	pool = encodeutils.safe_encode("ssds")
	vol_type = 2

hostname = os.uname()[1]

cleaners = []
for i in xrange(WORKERS):
        cleaner_name = hostname + '-' + str(i)
        cleaners.append(cleaner_name)

p = Pool(WORKERS)
p.map(workerd, cleaners)

#cnx.close()
