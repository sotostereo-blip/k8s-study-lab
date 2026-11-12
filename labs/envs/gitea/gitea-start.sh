#!/bin/sh
# Start Gitea as the image normally does, then create the lab admin user once.
/usr/bin/entrypoint /usr/bin/s6-svscan /etc/s6 &
pid=$!
until curl -fs http://localhost:3000/api/healthz >/dev/null 2>&1; do sleep 1; done
if ! curl -fs http://localhost:3000/api/v1/users/student >/dev/null 2>&1; then
  su git -c "gitea --config /data/gitea/conf/app.ini admin user create --admin \
    --username student --password studylab123 --email student@lab.local \
    --must-change-password=false" || echo "admin user not created"
fi
wait $pid
