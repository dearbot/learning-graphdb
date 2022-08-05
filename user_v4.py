#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import time
import json
import grequests
import requests
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed


# https://gql.readthedocs.io/en/v3.0.0a6/

token = ''
level = 0
timeout = 300  # minutes

###
TopUser_MAP={}
relations='' # relation records
users_path={} # user + json path
CURRENT_DIR="./data/jobs/"+os.getenv("GITHUB_RUN_NUMBER", "0")+"/"

class RunningInfo:
    status={}
    users={}
    status_latest=200
    waiting_start=0

    def save_s(self, status_code):
        if status_code not in self.status:
            self.status[status_code] = 0
        self.status[status_code]+=1
        self.status_latest=status_code
        if status_code == 403:
            self.waiting_start=time.time()
        else:
            self.waiting_start=0
    
    def update_waiting(self):
        self.waiting_start=time.time()

    def save_u(self, user):
        if not user:
            return
        u=user['login']
        if u not in self.users:
            self.users[u] = {}
        s=json.dumps(user)
        count=s.count('login')-1
        t = 1
        if 'count' in self.users[u]:
            count += self.users[u]['count']
            t += self.users[u]['time']
        self.users[u]={"count": count, "time": t}

    def output(self):
        with open('./data/README.md', 'a') as f:
            f.write('\n## Current Job %s \n\n' % os.getenv("GITHUB_RUN_NUMBER", ""))
            f.write("- status code: `%s`\n" % self.status)
            f.write("- user total count in this job: `%d`\n" % sum([v['count'] for k,v in self.users.items()]))
            if os.path.exists('/tmp/users.txt'):
                f.write("- user real count in this job: `%d`\n" % len(open('/tmp/users.txt','r').readlines()))
            f.write('\n## Detailed\n\n')
            f.write("current relations of users:\n\n")
            f.write('| No | User | Avatar | Follower | Following | Finished | Times | Count(L2) |\n')
            f.write('| -----: | :----- | ----: | ----: | ----: | :---- | ----: | :---- |\n')
            i = 1
            for k, v in TopUser_MAP.items():
                fin="False"
                if not v.get('followers', {}).get('pageInfo', {}).get('hasNextPage', False):
                    fin="<font color=yellow>True</font>"
                f.write('| %d | [%s<br>(%s)](https://github.com/%s) | <img alt=\'%s\' src="https://avatars.githubusercontent.com/u/%s?s=128&v=4" width="40px" /> | %s | %s | %s | %d | %d |\n' %(
                    i, 
                    v.get('name', '-'), k, k,
                    k, v.get('databaseId', '15368'),
                    v.get('followers', {}).get("totalCount", '0'),
                    v.get('following', {}).get("totalCount", '0'),
                    # use next curor check finish
                    fin,
                    self.users.get(k, {}).get('time', 0),
                    self.users.get(k, {}).get('count', 0),
                ))
                i+=1
                
    # call after move user to current job folder in github action        
    def output_jobs(self):
        total = 0
        with open('./data/README.md', 'a') as f:
            f.write('\n## Jobs Info\n\n')
            f.write('other jobs count:\n')
            f.write('| JobNo | Count |\n')
            f.write('| -----: | -----: |\n')

            # read from folder
            if os.path.exists('./data/jobs'):
                dirs=os.listdir('./data/jobs')
                for i in sorted([int(d) for d in dirs]):
                    i = str(i)
                    if os.path.isdir("./data/jobs/"+i):
                        f.write("| %s | %d |\n" % (i, len(os.listdir('./data/jobs/'+i))))
                        total += len(os.listdir('./data/jobs/'+i))
            f.write('| **total** | %d |\n' % (total))
            

# running
RI=RunningInfo()

###
# {
#   "errors": [
#     {
#       "type": "MAX_NODE_LIMIT_EXCEEDED",
#       "message": "This query requests up to 2,010,050 possible nodes which exceeds the maximum limit of 500,000."
#     }
#   ]
# }

# https://api.github.com/graphql 502
# {
#    "data": null,
#    "errors":[
#       {
#          "message":"Something went wrong while executing your query. This may be the result of a timeout, or it could be a GitHub bug. Please include `A39E:65C2:1A9544:24A927:612669EE` when reporting this issue."
#       }
#    ]
# }

# 403
# {
#     "documentation_url":"https://docs.github.com/en/free-pro-team@latest/rest/overview/resources-in-the-rest-api#secondary-rate-limits",
#     "message":"You have exceeded a secondary rate limit. Please wait a few minutes before you try again."
# }

def make_search_query():
    snode='''
    nodes {
        ... on User {
        id
        databaseId
        login
        name
        bio
        company
        location
        email
        twitterUsername
        createdAt
        updatedAt
        followers(first: 1) {
            totalCount
            pageInfo {
                hasNextPage
                endCursor
            }
        }
        following(first: 1) {
            totalCount
            pageInfo {
                hasNextPage
                endCursor
            }
        }
        }
    }
    '''
    query="""
    {
    viewer {
        login
    }
    rateLimit(dryRun: false) {
        cost
        limit
        nodeCount
        remaining
        resetAt
        used
    }
    search(query: "", type: USER, first: 100) {
        userCount
        %s
        pageInfo {
          endCursor
          hasNextPage
        }
    }
    }
    """
    # Y3Vyc29yOjEwMA==
    return query % (snode)

def make_search_query_w_cursor(cursor):
    snode='''
    nodes {
        ... on User {
        id
        databaseId
        login
        name
        bio
        company
        location
        email
        twitterUsername
        createdAt
        updatedAt
        followers(first: 1) {
            totalCount
            pageInfo {
                hasNextPage
                endCursor
            }
        }
        following(first: 1) {
            totalCount
            pageInfo {
                hasNextPage
                endCursor
            }
        }
        }
    }
    '''
    query="""
    {
    viewer {
        login
    }
    rateLimit(dryRun: false) {
        cost
        limit
        nodeCount
        remaining
        resetAt
        used
    }
    search(query: "", type: USER, first: 100, after: "%s") {
        userCount
        %s
        pageInfo {
          endCursor
          hasNextPage
        }
    }
    }
    """
    # Y3Vyc29yOjEwMA==
    return query % (cursor, snode)

def make_user_query_wo_cursor():
    query="""
    query($login: String! $n_of_followers:Int!) {
    rateLimit {
        cost
        limit
        nodeCount
        remaining
        resetAt
        used
    }
    user(login: $login) {
        id
        databaseId
        login
        name
        bio
        company
        location
        email
        twitterUsername
        createdAt
        updatedAt
        followers(first: $n_of_followers) {
            totalCount
            pageInfo {
                hasNextPage
                endCursor
            }
            nodes {
                id
                databaseId
                login
                name
                bio
                company
                location
                url
                email
                twitterUsername
                createdAt
                updatedAt
                followers(first: 10) {
                    totalCount
                    nodes {
                        id
                        databaseId
                        login
                        name
                        bio
                        company
                        location
                        email
                        twitterUsername
                        createdAt
                        updatedAt
                        followers(first: 1) {
                            totalCount
                             pageInfo {
                                hasNextPage
                                endCursor
                            }
                        }
                        following {
                            totalCount
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
                following {
                    totalCount
                }
            }
        }
        }
    }
    """
    return query

def make_user_query_w_cursor():
    query="""
    query($login: String! $n_of_followers:Int! $after: String!) {
    rateLimit {
        cost
        limit
        nodeCount
        remaining
        resetAt
        used
    }
    user(login: $login) {
        id
        databaseId
        login
        name
        bio
        company
        location
        email
        twitterUsername
        createdAt
        updatedAt
        followers(first: $n_of_followers after: $after) {
            totalCount
            pageInfo {
                hasNextPage
                endCursor
            }
            nodes {
                id
                databaseId
                login
                name
                bio
                company
                location
                email
                twitterUsername
                createdAt
                updatedAt
                followers(first: 10) {
                    totalCount
                    nodes {
                        id
                        databaseId
                        login
                        name
                        bio
                        company
                        location
                        email
                        twitterUsername
                        createdAt
                        updatedAt
                        followers(first: 1) {
                            totalCount
                            pageInfo {
                                hasNextPage
                                endCursor
                            }
                        }
                        following {
                            totalCount
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
                following {
                    totalCount
                }
            }
        }
        }
    }
    """
    return query

def make_user_variable(login, cursor=""):
    if cursor:
        return {
            "login": login,
            "after": cursor,
            "n_of_followers": 100,
        }
    else:
        return {
            "login": login,
            "n_of_followers": 100,
        }

def make_user(login, cursor=""):
    if cursor:
        return {
            "query": make_user_query_w_cursor(),
            "variables": make_user_variable(login, cursor) 
        }
    else:
        return {
            "query": make_user_query_wo_cursor(),
            "variables": make_user_variable(login, '') 
        }

def get_top_request(query):
    headers = {}
    if token:
        headers['Authorization'] = 'token ' + token
    # print(query)
    # exit(0)

    # ['hasNextPage'] ['startCursor']
    try:
        res=requests.post('https://api.github.com/graphql', headers=headers, json={'query': query})
        t=json.loads(res.text)
        
        if "errors" in t:
            print("get top", t)
        return t['data']['search']
    except Exception as e:
        print("get search", e)
        # {'data': None, 'errors': [{'message': 'Something went wrong while executing your query. This may be the result of a timeout, or it could be a GitHub bug. Please include `A192:7CFA:EB2D34:1B4927F:611B5598` when reporting this issue.'}]}
        return None

def proc_response(res, **kwargs):
    # do something ..
    X=json.loads(res.request.body).get('variables', {})
    print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),"🎵🎵 Response:", res.status_code, X, res.elapsed.total_seconds())
    RI.save_s(status_code=res.status_code)
    try:
        if res.status_code == 200:
            t=json.loads(res.text)
            r=t.get('data', {}).get('rateLimit', {})
            print("⚠️ rate", r)
            u=t.get('data', {}).get('user', {})
            if not u:
                # {'errors': [{'type': 'RATE_LIMITED', 'message': 'API rate limit exceeded for user ID XXXX.'}]}
                print(t)
                RI.update_waiting()
            save_data([u])
            RI.save_u(u)
    except Exception as e:
        print("proc_response", e)
    # make rework flag ready_fetch ...
    global TopUser_MAP
    n=X.get('login', '')
    print("top user", n)
    if n in TopUser_MAP:
        TopUser_MAP[n]['ready_fetch']=True
        print(n, "ready worker after response.")


def err_handler(request, exception):
    print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), "request error", exception)


def save_data(dat, root=True):
    if not dat:
        return
    if not os.path.exists(CURRENT_DIR):
        os.makedirs(CURRENT_DIR)
    for d in dat:
        if not d:
            continue
        user = d['login']
        if d.get('followers', {}).get('nodes', False):
            save_relation_data(user, 'follower', d['followers']['nodes'])
            save_data(d['followers']['nodes'], False)

        if d.get('following', {}).get('nodes', False):
            save_relation_data(user, 'following', d['following']['nodes'])
            save_data(d['following']['nodes'], False)
        
        global users_path
        path=CURRENT_DIR + user+'.json'
        if user not in users_path:
            with open('/tmp/users.txt', 'a') as f:
                f.write('{}\n'.format(user))
        else:
            # update history jobs data
            path=users_path[user]

        with open(path, 'w') as f:
            dd = copy.deepcopy(d)
            # remove nodes to save file
            if dd.get("followers", {}).get("nodes", []):
                del dd['followers']['nodes']
            f.write(json.dumps(dd, indent=2, ensure_ascii=False))
            users_path[user]=path
            
        if root:
            global TopUser_MAP
            TopUser_MAP[user]['ready_fetch']=True
            print(user, 'ready true')
        

def load_relation_data():
    if not os.path.exists("./relations/relations.txt"):
        return
    with open('./relations/relations.txt', 'r') as f:
        global relations
        relations = f.read()


def save_relation_data(user, relation, objects):
    # 〈tuple〉::=〈object〉‘#’〈relation〉‘@’〈user〉
    # 〈object〉::=〈namespace〉‘:’〈objectid〉
    # 〈user〉::=〈userid〉|〈userset〉
    # 〈userset〉::=〈object〉‘#’〈relation〉
    # https://research.google/pubs/pub48190/
    for i in objects:
        if not i:
            continue
        dd = "{}#{}@{}\n".format(i['login'], relation, user)
        global relations
        if dd not in relations:
            relations += dd


def output_relation():
    if not os.path.exists("./relations/"):
        os.makedirs("./relations/")
    with open('./relations/relations.txt', 'w') as f:
        global relations
        f.write(relations)


def load_top(top):
    t = []
    if not top:
        return t

    for d in top:
        if not d:
            continue
        if d['login'] not in users_path:
            t.append(d)
            continue
        with open(users_path[d['login']], 'r') as f:
            l = f.read()
            if l:
                l = json.loads(l)
                if l.get('followers', {}).get('pageInfo', {}):
                    print('read from history:', d['login'])
                    d["followers"]=l["followers"]
                else:
                    print('no pageinfo history:', d['login'])
            t.append(d)
    # update user
    for i in t:
        global TopUser_MAP
        i['ready_fetch']=True
        TopUser_MAP[i['login']]=i
    return t

def load_users_path():
    global users_path
    js = []
    if os.path.exists("./data/jobs"):
         js=["./data/jobs/"+i for i in os.listdir('./data/jobs')]
    for i in js:
        if os.path.isdir(i):
            us=os.listdir(i)
            for u in us:
                uu=u.split(".json")[0]
                if uu in users_path:
                    print("remove dup %s %s" % (i+"/"+u, users_path[uu]))
                    os.remove(i+"/"+u)
                    continue
                users_path[uu]=i+"/"+u
    print("user history count", len(users_path))
            

def proc_request(url, headers, json):
    if time.time() - RI.waiting_start < 60:
        # 60s in 403
        global TopUser_MAP
        print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), "❌ no send", json['variables'])
        TopUser_MAP[json['variables']['login']]['ready_fetch']=True
    else:
        print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), "🎈🎈 send", json['variables'])
        res=requests.post(url, headers=headers, json=json)
        proc_response(res)

def main_grequests():
    headers = {
        "User-Agent": "Awesome-Octocat-App"
    }
    if token:
        headers['Authorization'] = 'token ' + token
        
    with ThreadPoolExecutor(max_workers=100) as executor:
        while True:
            global TopUser_MAP
            if len(TopUser_MAP) == 0:
                break

            if not any([v.get('followers', {}).get('pageInfo', {}).get('hasNextPage', False) for v in TopUser_MAP.values()]):
                break

            global start_time
            if time.time() - start_time > timeout * 60:
                print("main_grequests timeout")
                executor.shutdown(wait=False, cancel_futures=True)
                break
            x={k:v for k, v in TopUser_MAP.items() if v.get('followers', {}).get('pageInfo', {}).get('hasNextPage', False)}
            if not any([v.get('ready_fetch', False) for k, v in x.items()]):
                print("💤💤 all no response to waiting...")
                time.sleep(2)
                continue

            x={k:v for k, v in x.items() if v.get('ready_fetch', False)}
            u=copy.deepcopy(x)
            print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), len(TopUser_MAP), len(u))

            # request
            timeout_flag=False
            for k, v in u.items():
                if not v.get('followers', {}).get('pageInfo', {}).get('hasNextPage', False):
                    # del TopUser_MAP[k]
                    # print(k, "finish")
                    continue
                if not v.get('ready_fetch', False):
                    continue
                
                # req=grequests.post(
                #     'https://api.github.com/graphql', 
                #     headers=headers, 
                #     json=make_user(k, v['followers']['pageInfo']['endCursor']),
                #     hooks={"response":proc_response})

                # time.sleep(2)
                # processes.append(executor.submit(grequests.map, [req], exception_handler=err_handler))

                executor.submit(proc_request, 
                    'https://api.github.com/graphql', 
                    headers=headers, 
                    json=make_user(k, v['followers']['pageInfo']['endCursor']))
                print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), "🧧🧧push queue", k, v['followers']['pageInfo']['endCursor'])
                TopUser_MAP[k]['ready_fetch']=False
                time.sleep(0.1)

                if time.time() - start_time > timeout * 60:
                    print("⛔⛔ make users timeout")
                    timeout_flag = True
                    break
                
            # timeout in request for loop
            if timeout_flag:
                print("⛔⛔ make users timeout exit")
                executor.shutdown(wait=False, cancel_futures=True)
                break
            print("new round")
            time.sleep(30)
        
    with open('./data/README.md', 'w') as f:
        f.write('## Github User Summary\n\n')
        f.write("- Top User Count: %d\n" % len(TopUser_MAP))
        f.write("- Relations: %d\n" % len(relations.split('\n')))
        f.write("- Real User Updated: %d\n" % len(users_path))


if __name__ == "__main__":
    # call output without args.
    if len(sys.argv) == 1:
        RI.output_jobs()
        exit(0)

    # args > 1 for processing
    if len(sys.argv) > 1:
        token = sys.argv[1]
    if len(sys.argv) > 2:
        timeout = int(sys.argv[2])
    start_time = time.time()

    # load users from jobs folders
    load_users_path()

    # top user from search query
    cursor="Y3Vyc29yOjEw"
    for i in range(2):
        print(i)
        query = make_search_query_w_cursor(cursor)
        top_data=get_top_request(query)
        # make global TOPUSERSS, reload the cursor from files.
        top=load_top(top_data['nodes'])
        if not top:
            print('top is null')
            exit(0)
        save_data(top)

        cursor=top_data['pageInfo']['endCursor']
        if not top_data['pageInfo']['hasNextPage']:
            break

    load_relation_data()
    main_grequests()
    output_relation()
    RI.output()
  
