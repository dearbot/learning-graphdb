#!/usr/bin/env python3
# coding: utf-8
import os
import sys
import time
import json
import grequests
import requests
import copy


### global
dgraph=''
finish=False

### param
url=""
x_auth_token=""
timeout = 300  # minutes


def fetchGraphQL(operationsDoc, operationName, variables):
    headers = {
        "Content-Type": "application/json"
    }
    if x_auth_token:
        headers['X-Auth-Token'] = x_auth_token

    try:
        res=requests.post(url, headers=headers, json={'query': operationsDoc, "variables": variables, "operationName": operationName})
        t=json.loads(res.text)
        if t.get("errors", []):
            print(t.get("errors"), [])
            global finish
            finish=True
        print(operationName)
        return [t['data']]
    except Exception as e:
        print("fetchGraphQL", e)
        # {'data': None, 'errors': [{'message': 'Something went wrong while executing your query. This may be the result of a timeout, or it could be a GitHub bug. Please include `A192:7CFA:EB2D34:1B4927F:611B5598` when reporting this issue.'}]}
        return None

    return 

addUserDoc = '''
mutation addOneUser($user: AddUserInput!) {
  addUser(input: [$user], upsert: true) {
    user {
      username
    }
  }
}
'''

add_variables={
  "user": {
      "username": "lisi",
      "displayName":"lisi",
      "followers": [
        {
          "username": "zhangsan"
        }
      ]
    }
}

updateUserDoc='''
mutation updateUser($user: String, $follower: String) {
  updateUser(input: {filter: {username: {eq: $user}}, set: {followers: {username: $follower}}}) {
    user {
      displayName
    }
  }
}
'''

update_variables={
  "user": "lisi",
  "follower": "lisi"
}


def save_dgraph(dat):
    if not dat:
        return
    for d in dat:
        if not d:
            continue
        if check_dgraph_history(d['login']):
            continue
        add_variables = {
            "user": {
                "username": d['login'],
                "displayName":d['name'],
                "avatarImg": d['avatarUrl'],
                "githubId": d.get('id', ''),
                "databaseId": d.get('databaseId', 0),
                "bio": d['bio'],
                "company": d['company'],
                "location": d['location'],
                "url": d['url'],
                "twitterUsername": d['twitterUsername'],
                "createdAt": d["createdAt"],
                "updatedAt": d["updatedAt"],
            }
        }
        fetchGraphQL(addUserDoc, 'addOneUser', add_variables)
        
        
def load_dgraph_data():
    if not os.path.exists("./dgraph/dgraph.txt"):
        return
    with open('./dgraph/dgraph.txt', 'r') as f:
        global dgraph
        dgraph = f.read()


def check_dgraph_history(user):
    return user in dgraph


def save_dgraph_history(user):
    dd = "{}\n".format(user)
    global dgraph
    if dd not in dgraph:
        dgraph += dd


def output_dgraph():
    if not os.path.exists("./dgraph/"):
        os.makedirs("./dgraph/")
    with open('./dgraph/dgraph.txt', 'w') as f:
        global dgraph
        f.write(dgraph)

        
def main():
    if not os.path.exists("./data/users"):
        print("data/users not exists")
        return
    user_json = os.listdir('./data/users')
    for u in user_json:
        if time.time() - start_time > timeout * 60:
            break
        if finish:
            return
        with open("./data/users/"+u, 'r') as f:
            d = f.read()
            d = json.loads(d)
            save_dgraph([d])
            save_dgraph_history(d['login'])
     

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("./main url token")
        exit(0)
    
    x_auth_token = sys.argv[2]
    url = sys.argv[1]

    if len(sys.argv) > 3:
        timeout = int(sys.argv[3])

    start_time = time.time()

    load_dgraph_data()
    main()
    output_dgraph()
