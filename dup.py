#!/usr/bin/env python3
# coding: utf-8
import os

users=os.listdir('./data/users')
if os.path.exists('./data/jobs'):
    dirs=os.listdir('./data/jobs')
    for d in dirs:
        td='./data/jobs/'+d
        if not os.path.isdir(td):
            continue
        us=os.listdir(td)
        for u in us:
            if u in users:
                uf=td+'/'+u
                print(uf)
                os.remove(uf)
            else:
                users.append(u)
