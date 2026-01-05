#!/bin/bash
cd /home/triskattie/fatsecret
source venv/bin/activate
fastapi run server.py &
/usr/bin/node index.js