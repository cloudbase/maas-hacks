#!/bin/bash

BASEDIR=$(dirname $0)

cd ~/maas

cp "$BASEDIR/vmrunapi.template" ~/maas/etc/maas/templates/power/
patch -p0 < "$BASEDIR/vmrun_power_schema.diff"

