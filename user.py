#!/usr/bin/env python3
# coding: utf-8
import os
import sys
import time
import json
import requests

url_keys = ['avatar_url', 
            'url',
            'html_url', 
            'followers_url', 
            'following_url', 
            'gists_url',
            'starred_url',
            'subscriptions_url', 
            'organizations_url', 
            'repos_url', 
            'events_url', 
            'received_events_url']
per_page = 100
sleep_time = 1
timeout = 300  # minutes

## global
# login, followers -1/finish, following -1/finish.
user_status = {}
relations = ''
starttime = time.time()


def save_user(dat):
    if not dat:
        return
    user = dat['login']
    if not os.path.exists("./data/users/"):
        os.makedirs("./data/users/")
    with open('./data/users/'+user+".json", 'w') as f:
        for k in url_keys:
            dat.pop(k, None)
        global user_status
        if user not in user_status:
            user_status[user] = dict()
        user_status[user]['self'] = True
        f.write(json.dumps(dat, indent=2))
        # print(user, "finished.")


def load_relation_data():
    if not os.path.exists("./data/relations/relations.txt"):
        return
    with open('./data/relations/relations.txt', 'r') as f:
        global relations
        relations = f.read()


def save_relation_data(user, relation, objects):
    # 〈tuple〉::=〈object〉‘#’〈relation〉‘@’〈user〉
    # 〈object〉::=〈namespace〉‘:’〈objectid〉
    # 〈user〉::=〈userid〉|〈userset〉
    # 〈userset〉::=〈object〉‘#’〈relation〉
    # https://research.google/pubs/pub48190/
    for i in objects:
        dd = "{}#{}@{}\n".format(i, relation, user)
        global relations
        if dd not in relations:
            relations += dd
    global user_status
    user_status[user][relation] = True


def output_relation():
    if not os.path.exists("./data/relations/"):
        os.makedirs("./data/relations/")
    with open('./data/relations/relations.txt', 'w') as f:
        f.write(relations)


def get_data(user):
    headers = {
        'Accept': 'application/vnd.github.v3+json',
    }
    if token:
        headers['Authorization'] = 'token ' + token
    res = requests.get("https://api.github.com/users/"+user, headers=headers)
    if res.status_code == 200:
        dat = res.json()
        save_user(dat)
        return True
    else:
        print(res.request.url, res.status_code)
        return False


def get_relations(user, relation='followers'):
    headers = {
        'Accept': 'application/vnd.github.v3+json'
    }
    if token:
        headers['Authorization'] = 'token ' + token
    i = 0
    users = []
    while True:
        params = {'per_page': per_page, 'page': i}
        res = requests.get("https://api.github.com/users/" +
                           user+"/"+relation, headers=headers, params=params)
        print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
              res.request.url, res.status_code)
        if res.status_code == 403:
            break
        if res.status_code == 200:
            dat = res.json()
            for d in dat:
                save_user(d)
                users.append(d['login'])
            if len(dat) != per_page:
                break
            i += 1
            # break # debug
            time.sleep(sleep_time)
        else:
            break
    return users


def followers(user):
    objects = get_relations(user, 'followers')
    if objects:
        relation = 'follower'
        save_relation_data(user, relation, objects)
        for u in objects:
            global user_status
            if user_status.get(u, {}).get(relation, False):
                print("{} already {}.".format(u, relation))
                continue
            time.sleep(sleep_time)
            # for more attributes
            get_data(u)
            if len(user_status.keys()) > max_size:
                return False
            if not followers(u):
                return False
        # timeout
        if time.time() - starttime > timeout * 60:
            return False
        return False
    else:
        return False

if __name__ == "__main__": 
    user = 'github'
    max_size = 1000
    token = ''
    if len(sys.argv) > 1 and sys.argv[1] != '':
        user = sys.argv[1]

    if len(sys.argv) > 2 and sys.argv[2] != '':
        max_size = int(sys.argv[2])

    if len(sys.argv) > 3 and sys.argv[3] != '':
        token = sys.argv[3]

    # main
    load_relation_data()
    r = get_data(user)
    if r:
        followers(user)
    output_relation()
    with open('./data/README.md', 'w') as f:
        f.write('## Github User Summary\n\n')
        f.write("- Relations: %d\n" % len(relations.split("\n")))
        f.write("- Real User Updated: %d\n" % len(os.listdir('./data/users')))
