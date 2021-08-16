# coding: utf-8

import os
import sys
import time
import requests
import json
import shutil

DATE=time.strftime("%Y%m%d", time.localtime()) 
LATEST_DIR="data/latest"
if not os.path.exists(LATEST_DIR):
    os.makedirs(LATEST_DIR)
    
###################################
# name: IP whitelist from Microsoft Azure
# Runs https://www.microsoft.com/en-us/download/confirmation.aspx?id=56519
# https://download.microsoft.com/download/7/1/D/71D86715-5596-4529-9B13-DA13A5DE5B63/ServiceTags_Public_20210822.json
###################################
DIR="data/microsoft"
if not os.path.exists(DIR):
    os.makedirs(DIR)
    
filename= DIR + "/" + "ServiceTags_Public_"+DATE+".json"
url="https://download.microsoft.com/download/7/1/D/71D86715-5596-4529-9B13-DA13A5DE5B63/ServiceTags_Public_"+DATE+".json"

r = requests.get(url)
if r.status_code == 200 and len(r.content) > 0:
  with open(filename, 'w') as f:
    f.write(json.dumps(r.json(), indent=2))

if os.path.exists(filename):
    shutil.copyfile(filename, LATEST_DIR+"/azure.json")
    
###################################
# name: github meta
# Runs https://api.github.com/meta
###################################
DIR="data/meta"
if not os.path.exists(DIR):
    os.makedirs(DIR)
url="https://api.github.com/meta"
filename=DIR+"/"+DATE+".json"

r = requests.get(url)
if r.status_code == 200 and len(r.content) > 0:
  with open(filename, 'w') as f:
    f.write(json.dumps(r.json(), indent=2))
    
if os.path.exists(filename):
    shutil.copyfile(filename, LATEST_DIR+"/github.json")
    
