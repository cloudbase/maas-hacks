#!/bin/bash

SCRIPT=$(readlink -f $0)
BASEDIR=$(dirname $SCRIPT)

cd ~/maas

cp "$BASEDIR/vmrunapi.template" ~/maas/etc/maas/templates/power/
patch -p0 < "$BASEDIR/vmrun_power_schema.diff"

