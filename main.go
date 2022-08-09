package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io/ioutil"
    "net/http"
    "os"
    "strconv"
    "strings"
    "sync"
    "time"
)

const (
    routineCountTotal = 100 //限制线程数
)

////////////////////////////
type Glimit struct {
    Num int
    C   chan struct{}
}

func NewG(num int) *Glimit {
    return &Glimit{
        Num: num,
        C : make(chan struct{}, num),
    }
}

func (g *Glimit) Run(f func()){
    g.C <- struct{}{}
    go func() {
        f()
        <-g.C
    }()
}

//////////////
func main() {
    argNum := len(os.Args)
    token:= ""
    intputTimeout:=1
    cursor:="" // for search Y3Vyc29yOjEw
    if argNum > 1 {
        token=os.Args[1]
    }
    if argNum > 2 {
        t, _ := strconv.Atoi(os.Args[2])
        intputTimeout=t
    }
    if argNum > 3 {
        cursor=os.Args[3]
    }

   var numberTasks = sync.Map{}

    wg1 := &sync.WaitGroup{}
    wg1.Add(1)
    go func() {
        makeUserHistoryPath()
        wg1.Done()
    }()
    wg1.Wait()

    wg1.Add(1)
    go func ()  {
        client := http.Client{}
        jsonStr := makeSearchRequestData(cursor)
        jsonString, err := json.Marshal(jsonStr)
        respBody, err := NumberQueryRequest(&client, token, jsonString)
        if err != nil {
            fmt.Printf("error: %s\n", err)
        } else {
            sr:=SearchResponse{}
            json.Unmarshal(respBody, &sr)
            if len(sr.Errors) != 0 {
                fmt.Println(sr.Errors[0].Message)
            }
            fmt.Printf("%d nodes\n", len(sr.Data.Search.Nodes))
            for _, v := range sr.Data.Search.Nodes {
                numberTasks.Store(v.Login, "")
                // get the history endCursor
                if file, ok := UserHistoryPath.Load(v.Login); ok {
                    // in
                    // read the history cursor replace
                    jsonFile, err := os.Open(file.(string))
                    if err != nil {
                        fmt.Println(err)
                    }
                    defer jsonFile.Close()
                    byteValue, _ := ioutil.ReadAll(jsonFile)
                    var user Node
                    json.Unmarshal([]byte(byteValue), &user)
                    if user.Followers.PageInfo.HasNextPage {
                        numberTasks.Store(v.Login, user.Followers.PageInfo.EndCursor)
                    }
                } 	
            }
        }
        wg1.Done()
    }() 
    wg1.Wait()

    lens := 0
    numberTasks.Range(func(key, value interface{}) bool {
        lens++
        return true
    })
    fmt.Printf("goto loop %d\n", lens)

    timeout := time.After(time.Minute * time.Duration(intputTimeout))
    finish := make(chan bool)
    go func() {
        for {
            select {
            case <-timeout:
                fmt.Println("timeout")
                finish <- true
                return
            default:
                g := NewG(routineCountTotal)
                wg := &sync.WaitGroup{}
                beg := time.Now()
                numberTasks.Range(func(login, endCursor interface{}) bool {
                    wg.Add(1)
                    g.Run(func() {
                        client := http.Client{}
                        fmt.Printf("%s %s request\n", login.(string), endCursor.(string))
                        jsonStr := makeUserRequestData(login.(string), endCursor.(string))
                        jsonString, err := json.Marshal(jsonStr)
                        respBody, err := NumberQueryRequest(&client, token, jsonString)
                        if err != nil {
                            fmt.Printf("error: %s %s\n", login, err)
                        } else {
                            ur:=UserResponse{}
                            json.Unmarshal(respBody, &ur)
                            fmt.Printf("%s response\n", ur.Data.User.Login)
                            // to save file and datas
                            saveUserToFile(ur.Data.User, true)
                        }
                        wg.Done()
                    })
                    time.Sleep(time.Duration(1000)*time.Millisecond)
                    return true
                })
                wg.Wait()

                fmt.Printf("time consumed: %fs\n", time.Now().Sub(beg).Seconds())
                lens := 0
                NextNumberTasks.Range(func(key, value interface{}) bool {
                    lens++
                    return true
                })
                fmt.Printf("len(NextNumberTasks)=%d, current users=%d\n", lens, UserCountThisJob)
                dump(ResponseInfo)
                numberTasks=NextNumberTasks
            }// select
        }//for
    }()
 
    <-finish
    fmt.Println("Finish")
}

var NextNumberTasks = sync.Map{}
var UserHistoryPath = sync.Map{}
var ResponseInfo = sync.Map{}
var UserHistoryUsed = sync.Map{}
var UserCountThisJob = 0


type UserResponse struct {
    Data struct {
        RateLimit struct {
            Cost      int       `json:"cost"`
            Limit     int       `json:"limit"`
            NodeCount int       `json:"nodeCount"`
            Remaining int       `json:"remaining"`
            ResetAt   time.Time `json:"resetAt"`
            Used      int       `json:"used"`
        } `json:"rateLimit"`
        User Node `json:"user"`
    } `json:"data"`
    Errors []Error `json:"errors"`
}

type Node struct {
    ID              string    `json:"id"`
    DatabaseID      int       `json:"databaseId"`
    Login           string    `json:"login"`
    Name            string    `json:"name"`
    Bio             string    `json:"bio"`
    Company         string    `json:"company"`
    Location        string    `json:"location"`
    Email           string    `json:"email"`
    TwitterUsername string    `json:"twitterUsername"`
    CreatedAt       time.Time `json:"createdAt"`
    UpdatedAt       time.Time `json:"updatedAt"`
    Followers       struct {
        TotalCount int `json:"totalCount"`
        Nodes      []Node `json:"nodes"`
        PageInfo   struct {
            HasNextPage bool   `json:"hasNextPage"`
            EndCursor   string `json:"endCursor"`
        } `json:"pageInfo"`
    } `json:"followers"`
    Following struct {
        TotalCount int `json:"totalCount"`
        PageInfo   struct {
            HasNextPage bool   `json:"hasNextPage"`
            EndCursor   string `json:"endCursor"`
        } `json:"pageInfo"`
    } `json:"following"`
}

type SearchResponse struct {
    Data struct {
        Viewer struct {
            Login string `json:"login"`
        } `json:"viewer"`
        RateLimit struct {
            Cost      int       `json:"cost"`
            Limit     int       `json:"limit"`
            NodeCount int       `json:"nodeCount"`
            Remaining int       `json:"remaining"`
            ResetAt   time.Time `json:"resetAt"`
            Used      int       `json:"used"`
        } `json:"rateLimit"`
        Search struct {
            UserCount int `json:"userCount"`
            Nodes     []Node `json:"nodes"`
            PageInfo struct {
                EndCursor   string `json:"endCursor"`
                HasNextPage bool   `json:"hasNextPage"`
            } `json:"pageInfo"`
        } `json:"search"`
    } `json:"data"`
    Errors []Error `json:"errors"`
}

type Error struct {
    Type 	string `json:"type"`
    Message string `json:"message"`
}

type RequestData struct {
    Query string `json:"query"`
    Variables struct {
        Login string `json:"login"`
        After string `json:"after"`
    } `json:"variables"`
}

func NumberQueryRequest(client *http.Client, token string, jsonStr []byte) (body []byte, err error) {
    url := "https://api.github.com/graphql"
    req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonStr))
    if err != nil {
        return nil, err
    }
    req.Header.Set("Authorization", fmt.Sprintf("token %s", token))
    req.Header.Set("User-Agent", "Awesome-Octocat-App")
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    
    statusCode := strconv.Itoa(resp.StatusCode)
    if c, ok := ResponseInfo.Load(statusCode); ok {
        //do something here
        ResponseInfo.Store(strconv.Itoa(resp.StatusCode), c.(int)+1)
    } else {
        ResponseInfo.Store(strconv.Itoa(resp.StatusCode), 0)
    }

    if resp.StatusCode != http.StatusOK {
        data, _ := ioutil.ReadAll(resp.Body)
        // reworker
        requestData:=RequestData{}
        json.Unmarshal(jsonStr, &requestData)
        NextNumberTasks.Store(requestData.Variables.Login, requestData.Variables.After)
        return nil, fmt.Errorf("rework: response code is %d, body:%s", resp.StatusCode, string(data))
    }
    if resp != nil && resp.Body != nil {
        defer resp.Body.Close()
    }
    body, err = ioutil.ReadAll(resp.Body)
    if err != nil {
        return nil, err
    }
    return body, nil
}

func makeUserRequestData(login, cursor string) map[string]interface{} {
    query:=`
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
    `

    query_wo_cursor:=`
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
    `

    if (cursor != "") {
        return map[string]interface{}{
            "query": query,
            "variables": map[string]interface{}{
                "login": login,
                "after": cursor,
                "n_of_followers": 100,
            },
        }
    } else {
        return map[string]interface{}{
            "query": query_wo_cursor,
            "variables": map[string]interface{}{
                "login": login,
                "n_of_followers": 100,
            },
        }
    }
}

func makeSearchRequestData(cursor string) map[string]interface{} {
    query:=	`
    query($after: String!) {
        viewer {
            login
        }
        rateLimit {
            cost
            limit
            nodeCount
            remaining
            resetAt
            used
        }
        search(query: "", type: USER, first: 100, after: $after) {
            userCount
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
            pageInfo {
              endCursor
              hasNextPage
            }
        }
        }
    `

    query_wo_cursor:=	`
    query {
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
            pageInfo {
              endCursor
              hasNextPage
            }
        }
        }
    `

    if (cursor != "") {
        return map[string]interface{}{
            "query": query,
            "variables": map[string]interface{}{
                "after": cursor,
            },
        }
    } else {
        return map[string]interface{}{
            "query": query_wo_cursor,
            "variables": map[string]interface{}{
            },
        }
    }
}

func saveUserToFile(node Node, top bool) {
    currentPath := "./data/jobs/0/"
    if os.Getenv("GITHUB_RUN_NUMBER") != "" {
        currentPath = fmt.Sprintf("./data/jobs/%s/", os.Getenv("GITHUB_RUN_NUMBER"))
    }
    os.MkdirAll(currentPath, 0777)
    UserCountThisJob += 1
    // check histroy 
    // fatal error: concurrent map read and map write
    if file, ok := UserHistoryPath.Load(node.Login); ok {
       if _, found := UserHistoryUsed.Load(node.Login); !found {
            // in
            // read the history cursor replace
            jsonFile, err := os.Open(file.(string))
            if err != nil {
                fmt.Println(err)
            }
            defer jsonFile.Close()
            byteValue, _ := ioutil.ReadAll(jsonFile)
            var user Node
            json.Unmarshal([]byte(byteValue), &user)
            node.Followers.PageInfo=user.Followers.PageInfo
            UserHistoryUsed.Store(node.Login, "used")
       } else {
            nodeNew := new(Node)
            *nodeNew = node
            nodeNew.Followers.Nodes=nil
            fileData, _ := json.MarshalIndent(nodeNew, "", " ")
            _ = ioutil.WriteFile(file, fileData, 0777)
       }
    } else {
        // not in or used
        path := fmt.Sprintf("%s/%s.json", currentPath, node.Login)
        nodeNew := new(Node)
        *nodeNew = node
        nodeNew.Followers.Nodes=nil
        fileData, _ := json.MarshalIndent(nodeNew, "", " ")
        _ = ioutil.WriteFile(path, fileData, 0777)
    }

    for _, v := range node.Followers.Nodes {
        saveUserToFile(v, false)
    }

    if top && node.Followers.PageInfo.HasNextPage {
        // put queue
        NextNumberTasks.Store(node.Login, node.Followers.PageInfo.EndCursor)
    }
}

func makeUserHistoryPath() {
    os.MkdirAll("./data/jobs", 0777)
    dirs, err := ioutil.ReadDir("./data/jobs")
    if err != nil {
        fmt.Printf(err.Error())
    }

    for _, d := range dirs {
        files, err := ioutil.ReadDir(fmt.Sprintf("./data/jobs/%s/", d.Name()))
        if err != nil {
            fmt.Printf(err.Error())
        }
        for _, file := range files {
            login :=strings.Split(file.Name(), ".json")[0]
            if hf, found := UserHistoryPath(login); found {
                os.Remove(hf)
            } else {
                UserHistoryPath.Store(login, fmt.Sprintf("./data/jobs/%s/%s", d.Name(), file.Name()))
            }
        }
    }
}

func dump(data sync.Map){
    m := map[string]interface{}{}
    data.Range(func(key, value interface{}) bool {
        m[fmt.Sprint(key)] = value
        return true
    })
    b,_:=json.MarshalIndent(m, "", "  ")
    fmt.Println(string(b))
}
