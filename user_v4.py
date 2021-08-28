#!/usr/bin/env python3
# coding: utf-8
import os
import sys
import time
import json
import grequests
import requests
import copy

# https://gql.readthedocs.io/en/v3.0.0a6/


token = ''
level = 0
timeout = 300  # minutes

###
top_user_map={}
relations=''
users={} # user + json path
reqs=[]
current_dir="./data/jobs/"+os.getenv("GITHUB_RUN_NUMBER", "0")+"/"

class RunningInfo:
    status={}
    users={}

    def save_s(self, status_code):
        if status_code not in self.status:
            self.status[status_code] = 0
        self.status[status_code]+=1

    def save_u(self, user):
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
                f.write("- user real count in this job: %d\n" % len(open('/tmp/users.txt','r').readlines()))
            f.write('\n## Detailed\n\n')
            f.write("current relations of users:\n\n")
            f.write('| No | User | Times | Count(L2) | Avatar | Follower | Following |\n')
            f.write('| -----: | :-----| ----: | ----: | ---- | ----: | ----: |\n')
            i = 1
            for k, v in self.users.items():
                f.write('| %d | %s | %d | %d | <img alt=\'%s\' src="%s" width="40px" /> | %s | %s |\n' %(i, k, v['time'], v['count'], 
                k,
                top_user_map.get(k, {}).get('avatarUrl', 'https://avatars.githubusercontent.com/in/15368?s=64&v=4'),
                top_user_map.get(k, {}).get('followers', {}).get("totalCount", '0'),
                top_user_map.get(k, {}).get('following', {}).get("totalCount", '0')
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
            if os.path.exists('./data/jobs'):
                dirs=os.listdir('./data/jobs')
                for i in sorted([int(d) for d in dirs]):
                    i = str(i)
                    if os.path.isdir("./data/jobs/"+i):
                        f.write("| %s | %d |\n" % (i, len(os.listdir('./data/jobs/'+i))))
                        total += len(os.listdir('./data/jobs/'+i))
            f.write("| %s | %d |\n" % ('users', len(os.listdir('./data/users'))))
            total += len(os.listdir('./data/users'))
            f.write('| %s | %d |\n' % ('total', total))
            

# running
running=RunningInfo()

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

def make_query():
    snode='''
    nodes {
        ... on User {
        id
        databaseId
        login
        name
        bio
        avatarUrl(size: 40)
        company
        location
        url
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
    search(query: "", type: USER, first: 100, after: "Y3Vyc29yOjEwMA==") {
        userCount
        %s
    }
    }
    """
    return query % (snode)

def make_user_query_wo_cursor():
    query="""
    query($login: String! $number_of_followers:Int!) {
    user(login: $login) {
        id
        databaseId
        login
        name
        bio
        avatarUrl(size: 40)
        company
        location
        url
        twitterUsername
        createdAt
        updatedAt
        followers(first: $number_of_followers) {
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
                avatarUrl(size: 40)
                company
                location
                url
                twitterUsername
                createdAt
                updatedAt
                followers(first: 20) {
                    totalCount
                    nodes {
                        id
                        databaseId
                        login
                        name
                        bio
                        avatarUrl(size: 40)
                        company
                        location
                        url
                        twitterUsername
                        createdAt
                        updatedAt
                        followers {
                            totalCount
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
    query($login: String! $number_of_followers:Int! $after: String!) {
    user(login: $login) {
        id
        databaseId
        login
        name
        bio
        avatarUrl(size: 40)
        company
        location
        url
        twitterUsername
        createdAt
        updatedAt
        followers(first: $number_of_followers after: $after) {
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
                avatarUrl(size: 40)
                company
                location
                url
                twitterUsername
                createdAt
                updatedAt
                followers(first: 20) {
                    totalCount
                    nodes {
                        id
                        databaseId
                        login
                        name
                        bio
                        avatarUrl(size: 40)
                        company
                        location
                        url
                        twitterUsername
                        createdAt
                        updatedAt
                        followers {
                            totalCount
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
            "number_of_followers": 100,
        }
    else:
        return {
            "login": login,
            "number_of_followers": 100,
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

def get_top(query):
    headers = {}
    if token:
        headers['Authorization'] = 'token ' + token
    # print(query)
    # exit(0)

    # ['hasNextPage'] ['startCursor']
    try:
        res=requests.post('https://api.github.com/graphql', headers=headers, json={'query': query})
        t=json.loads(res.text)
        return t['data']['search']['nodes']
    except Exception as e:
        print(e)
        # {'data': None, 'errors': [{'message': 'Something went wrong while executing your query. This may be the result of a timeout, or it could be a GitHub bug. Please include `A192:7CFA:EB2D34:1B4927F:611B5598` when reporting this issue.'}]}
        return None

def get_user(gql):
    headers = {}
    if token:
        headers['Authorization'] = 'token ' + token
    try:
        res=requests.post('https://api.github.com/graphql', headers=headers, json=gql)
        t=json.loads(res.text)
        return [t['data']['user']]
    except Exception as e:
        print("get_user", e)
        # {'data': None, 'errors': [{'message': 'Something went wrong while executing your query. This may be the result of a timeout, or it could be a GitHub bug. Please include `A192:7CFA:EB2D34:1B4927F:611B5598` when reporting this issue.'}]}
        return None

def proc_response(res, **kwargs):
    # do something ..
    print("== Response:", res.status_code)
    running.save_s(status_code=res.status_code)
    try:
        if res.status_code != 200:
            X=json.loads(res.request.body)
            print(X.get('variables', {}))
            global reqs
            reqs.append(X.get('variables', {}))
            return
        t=json.loads(res.text)
        u=t.get('data', {}).get('user', {})
        save_data([u])
        running.save_u(u)
        if not u:
            print(t)
    except Exception as e:
        print("proc_response", e)


def err_handler(request, exception):
    print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), "request error", exception)

def get_users(u):
    headers = {}
    if token:
        headers['Authorization'] = 'token ' + token

    req_list = []
    for k, v in u.items():
        if not v.get('followers', {}).get('pageInfo', {}).get('hasNextPage', False):
            del top_user_map[k]
            print(k, "finish")
            continue
        req=grequests.post(
            'https://api.github.com/graphql', 
            headers=headers, 
            json=make_user(k, v['followers']['pageInfo']['endCursor']),
            hooks={"response":proc_response})
        req_list.append(req)
    
    # retry failed
    if reqs:
        for r in reqs[:10]:
            print("RETRY →", r)
            req=grequests.post(
                'https://api.github.com/graphql', 
                headers=headers, 
                json=r,
                hooks={"response":proc_response})
            req_list.append(req)

    grequests.map(req_list, size=10, exception_handler=err_handler)


def save_data(dat, root=True):
    if not dat:
        return
    if not os.path.exists(current_dir):
        os.makedirs(current_dir)
    for d in dat:
        if not d:
            continue
        user = d['login']
        if d.get('followers', {}).get('nodes', False):
            save_relation_data(user, 'follower', d['followers']['nodes'])
            save_data(d['followers']['nodes'], False)

        if d.get('following', {}).get('nodes', False):
            save_relation_data(user, 'followling', d['followling']['nodes'])
            save_data(d['following']['nodes'], False)
        
        global users
        path=current_dir + user+'.json'
        if user not in users:
            with open('/tmp/users.txt', 'a') as f:
                f.write('{}\n'.format(user))
        else:
            # update history data
            path=users[user]

        with open(path, 'w') as f:
            dd = copy.deepcopy(d)
            # remove nodes to save file
            if dd.get("followers", {}).get("nodes", []):
                del dd['followers']['nodes']
            f.write(json.dumps(dd, indent=2, ensure_ascii=False))
            users[user]=path
            if root:
                global top_user_map
                top_user_map[user]=d
        

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
        dd = "{}#{}@{}\n".format(i['login'], relation, user)
        global relations
        if dd not in relations:
            relations += dd


def output_relation():
    if not os.path.exists("./data/relations/"):
        os.makedirs("./data/relations/")
    with open('./data/relations/relations.txt', 'w') as f:
        global relations
        f.write(relations)


def load_top(top):
    t = []
    if not top:
        return t

    for d in top:
        if not d:
            continue
        if d['login'] not in users:
            t.append(d)
            continue
        with open(users[d['login']], 'r') as f:
            l = f.read()
            l = json.loads(l)
            if l.get('followers', {}).get('pageInfo', {}):
                print('read from history:', d['login'])
                t.append(l)
            else:
                print('no pageinfo history:', d['login'])
                t.append(d)
    return t

def main():
    while True:
        global top_user_map
        u=copy.deepcopy(top_user_map)
        print("top user count:", len(top_user_map))
        if time.time() - start_time > timeout * 60:
            print("timeout")
            break
        for k, v in u.items():
            if not v['followers']['pageInfo']['hasNextPage']:
                del top_user_map[k]
                print("finish for followers: ", k)
                continue
            d=get_user(make_user(k, v['followers']['pageInfo']['endCursor']))
            save_data(d)

            with open('./data/README.md', 'w') as f:
                f.write('## Github User Summary\n\n')
                f.write("- Top User Count: %d\n" % len(top_user_map))
                f.write("- Relations: %d\n" % len(relations.split('\n')))
                f.write("- Real User Updated: %d\n" % len(users))
            output_relation()
        if len(top_user_map) == 0:
            break

def load_users():
    global users
    js = []
    if os.path.exists("./data/jobs"):
        js=["./data/jobs/"+i for i in os.listdir('./data/jobs')]
    for i in ['./data/users']+js:
        if os.path.isdir(i):
            us=os.listdir(i)
            for u in us:
                uu=u.split(".json")[0]
                if uu in users:
                    print("remove dup %s %s" % (i+"/"+u, users[uu]))
                    os.remove(i+"/"+u)
                    continue
                users[uu]=i+"/"+u
    print("user history count", len(users))
            

def main_grequests():
    while True:
        split_count = 20
        for i in range(split_count):
            u={key: value for ii, (key, value) in enumerate(top_user_map.items()) if ii % split_count == i}
            print(
                "[%s] top user count: %s count=%s %s/%s" %
                (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                len(top_user_map), len(u), i+1, split_count))
            time.sleep(3)
            if time.time() - start_time > timeout * 60:
                print("timeout")
                return
            res=get_users(u)
            with open('./data/README.md', 'w') as f:
                f.write('## Github User Summary\n\n')
                f.write("- Top User Count: %d\n" % len(top_user_map))
                f.write("- Relations: %d\n" % len(relations.split('\n')))
                f.write("- Real User Updated: %d\n" % len(users))
            output_relation()
            if len(top_user_map) == 0:
                return


if __name__ == "__main__":
    # call output without args.
    if len(sys.argv) == 1:
        running.output_jobs()
        exit(0)
    if len(sys.argv) > 1:
        token = sys.argv[1]
    if len(sys.argv) > 2:
        timeout = int(sys.argv[2])
    start_time = time.time()

    load_users()

    query = make_query()
    top=get_top(query)
    top=load_top(top)
    if not top:
        print('top is null')
        exit(0)
    
    save_data(top)

    load_relation_data()
    main_grequests()
    output_relation()
    running.output()
