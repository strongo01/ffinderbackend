#!/bin/bash
cd /home/triskattie/fatsecret
source venv/bin/activate
python server.py &
/usr/bin/node index.js