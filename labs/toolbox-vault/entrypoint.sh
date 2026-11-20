#!/bin/bash
lab-init >/var/log/lab-init.log 2>&1 &
exec ttyd -W -p 7681 -t fontSize=14 -t titleFixed="vault lab" bash
