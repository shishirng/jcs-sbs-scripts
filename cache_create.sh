#!/bin/bash

#***ALL GLOBALS go here***
CEPH_HOST=""
HOST=""
USERNAME=""
PASSWORD=""

USAGE="Incorrect usage. Expected \n $0 <glance_id> <min_size> <path_to_image>"

if [ "$#" -ne 3 ]; then
	echo -e $USAGE
        exit
fi

GLANCE_ID=$1
MIN_SIZE=$2
IMAGE_PATH=$3

echo -e "GlanceID is: $GLANCE_ID"
echo -e "Min_Size is: $MIN_SIZE"
echo -e "Image location is: $IMAGE_PATH"

read -p "Do you wish to continue creating the cache(y|n)? " answer
case ${answer:0:1} in
	y|Y )
		echo "Starting cache creation - 6 step process"
	;;
	n|N )
		echo "exiting"
		exit
	;;
	* )
		echo "Incorrect choice, please select y|n"
		exit
esac

if [ ! -f $IMAGE_PATH ]; then
	echo -e "File $IMAGE_PATH does not exist"
	exit
fi

#*************************#
echo -e "\n*****Step 1: creating db entry for volume*****"

VOLUME_UUID=$(uuidgen)
echo "volume-id: $VOLUME_UUID"

volume_display_name=$GLANCE_ID
volume_display_name+="_cache_volume"
echo "display_name: $volume_display_name"

mysql -h $HOST -u $USERNAME -p$PASSWORD -D cinder -bse "INSERT into volumes (created_at, updated_at, deleted, status, id, size, host, availability_zone, attach_status, display_name, bootable) VALUES (now(), now(), 0, 'creating', '$VOLUME_UUID', '$MIN_SIZE', '$CEPH_HOST', 'nova', 'detached', '$volume_display_name', 1)"

if [ $? -eq 0 ]; then
	echo -e "Created db entry for volume successfully"
else
	echo -e "Failed to create db entry for volume $VOLUME_UUID. Please clean it up"
	exit
fi

#*************************#
echo -e "\n*****Step 2: importing image to ceph*****"
echo -e "Step 2: This may take time based on image size"

size_in_gb=$MIN_SIZE
size_in_gb+="G"

volume_name="volume-"
volume_name+=$VOLUME_UUID
echo -e "creating $volume_name of size $size_in_gb in ceph"

rbd --conf /etc/ceph/ceph.conf --id cinder --keyring /etc/ceph/ceph.client.cinder.keyring import --image-format 2 --pool sbs $IMAGE_PATH $volume_name
if [ $? -eq 0 ]; then
	echo -e "Created volume successfully"
else
	echo -e "Failed to create volume $VOLUME_UUID"
	exit
fi

size_in_mb=$(($MIN_SIZE * 1024))
echo -e "resize volume to $size_in_gb"

rbd --conf /etc/ceph/ceph.conf --id cinder --keyring /etc/ceph/ceph.client.cinder.keyring --pool sbs resize --size $size_in_mb $volume_name
 
if [ $? -eq 0 ]; then
        echo -e "resized volume successfully"
else
        echo -e "Failed to resize volume $VOLUME_UUID"
        exit
fi

#*************************#
echo -e "\n*****Step 3: creating db entry for snapshot*****"
SNAPSHOT_UUID=$(uuidgen)
echo "snapshot-id: $SNAPSHOT_UUID"

snapshot_display_name=$GLANCE_ID
snapshot_display_name+="_snap_volume"
echo "snapshot display_name: $snapshot_display_name"

mysql -h $HOST -u $USERNAME -p$PASSWORD -D cinder -bse "INSERT into snapshots (created_at, updated_at, deleted, status, progress, id, volume_size, display_name, volume_id) VALUES (now(), now(), 0, 'creating', '0%', '$SNAPSHOT_UUID', '$MIN_SIZE', '$snapshot_display_name', '$VOLUME_UUID')"

if [ $? -eq 0 ]; then
	echo -e "Created db entry for snapshot successfully"
else
	echo -e "Failed to create db entry for snapshot $SNAPSHOT_UUID."
	exit
fi

#*************************#
echo -e "\n*****Step 4-a: creating snapshot for volume in ceph*****"
snapshot_name="snapshot-"
snapshot_name+=$SNAPSHOT_UUID
echo -e "creating snapshot $snapshot_name for $volume_name"

rbd --conf /etc/ceph/ceph.conf --id cinder --keyring /etc/ceph/ceph.client.cinder.keyring --pool sbs snap create $volume_name@$snapshot_name
if [ $? -eq 0 ]; then
	echo -e "Created snapshot successfully"
else
	echo -e "Failed to create snapshot $volume_name@$snapshot_name"
	exit
fi


#*************************#
echo -e "\n*****Step 4-b: protecting snapshot for volume in ceph*****"
rbd --conf /etc/ceph/ceph.conf --id cinder --keyring /etc/ceph/ceph.client.cinder.keyring --pool sbs snap protect $volume_name@$snapshot_name
if [ $? -eq 0 ]; then
	echo -e "Protected snapshot successfully"
else
	echo -e "Failed to protect snapshot $volume_name@$snapshot_name"
	exit
fi

#*************************#
echo -e "\n*****Step 5: Making snapshot available*****"

mysql -h $HOST -u $USERNAME -p$PASSWORD -D cinder -bse "UPDATE snapshots SET status='available',progress='100%' WHERE id='$SNAPSHOT_UUID'"
if [ $? -eq 0 ]; then
        echo -e "Updated db entry for snapshot successfully"
else
        echo -e "Failed to update db entry for snapshot $SNAPSHOT_UUID."
        exit
fi

#*************************#
echo -e "\n*****Step 6: Making volume available*****"

mysql -h $HOST -u $USERNAME -p$PASSWORD -D cinder -bse "UPDATE volumes SET status='available' WHERE id='$VOLUME_UUID'"
if [ $? -eq 0 ]; then
        echo -e "Updated db entry for volumes successfully"
else
        echo -e "Failed to update db entry for volume $VOLUME_UUID."
        exit
fi

