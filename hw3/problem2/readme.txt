
#1 Schema Design Decisions
**Partition keys  structure
- *PK: Groups papers by research category
- *SK: Combines publication date and ArXiv ID for sorting / uniqueness

**Global Secondary Indexes - 3 used
- **AuthorIndex Retrieve all papers by a given author in chronological order
- **PaperIdIndex Lookup by exact ArXiv ID
- **KeywordIndex Enables keyword-based discovery

** denormalization trade offs
- *P PaperIdItem
- *C CategoryItems one by category
- *A AuthorItems one by authot
- *K KeywordItems top10



#2 Denormalization Analysis 
- *Papers loaded: N
- *Total items written: M
- *Denormalization factor: M / N (= P+C + A + K)
- *which access patterns caused the most duplication?
counts per Category/Author/Keyword/Canonical and per-paper averages

# 3 Query Limitations
## Query Limitations
- **Global aggregates reduceextra tables
- **Complex multikeyword search minimize the  search/ denormalize combinations


#4 When to Use DynamoDB vs PostgreSQL
- *DynamoDB when:
  - known, high-traffic access patterns that map to primary/secondary keys.
  - You can accept denormalization and eventual consistency on indexes.
  - You value operational simplicity (serverless, no cluster to manage).

- *PostgreSQL when:
  - You need complex queries, joins, complex aggregations across entities.
  - You need strong multi-row/ multi-table transactions
  - Scale is moderate and flexibility is more important

#5 EC2 Deployment
  - Your EC2 instance public IP:  18.191.177.127
  - IAM role ARN used: arn:aws:iam::428146723511:role/Loader
  - Any challenges encountered during deployment: lotss

1 boto3 raised authentication errors when trying to write to DynamoDB
2 running python api_server.py 8080 caused: OSError: [Errno 98] Address already in use
3 dynamoDB region misconfiguration
4 The SCP command was run inside the EC2 shell, where path :\Users\Leonardo\Downloads\loaderkeys.pem don’t exist.
Solution: Exited the EC2 session and ran scp from PowerShell 
5 The data file (papers.json) wasn’t in the correct directory on the EC2 instance. solution 
Used scp to upload the file to the EC2 home directory and updated the command
6 After reconnecting to EC2, the virtual environment (venv) was inactive, causing missing package errors.  
Solution:  Reactivated it manually before running Python scripts:
7 python api_server.py took a long time to start
8 missing scripts: The file hadn’t been uploaded to the EC2 instance.  Solution:  Uploaded it using SCP
9  This was one tough,mixing commands between Windows PowerShell and Ubuntu  caused confusion and file not found messages. It was very confusing while trying to figure out what wasnt working. The solution keepclear distinction:
* run scp and ssh commands from PowerShell
* run Python and AWS commands inside EC2 Ubuntu

10 

HOw to run on EC2
# region set for shell
export AWS_REGION=us-west-2
export TABLE_NAME=arxiv-papers

# stop any old server on 8080
pkill -f api_server.py || true

# start the server in background
nohup python3 api_server.py 8080 > server.log 2>&1 &

# verify locally on the EC2
curl "http://localhost:8080/papers/recent?category=cs.LG&limit=1"

### verifying endpoints
# 1 cent in category
curl "http://localhost:8080/papers/recent?category=cs.LG&limit=3"

# 2 by author
curl "http://localhost:8080/papers/author/hendrik%20blockeel"

# 3 by ID 
curl "http://localhost:8080/papers/0110036v1"

# 4 date range
curl "http://localhost:8080/papers/search?category=cs.LG&start=2001-10-01&end=2001-10-31"

# 5 by keyword
curl "http://localhost:8080/papers/keyword/efficient?limit=5"

And this are the results:
(venv) ubuntu@ip-172-31-26-191:~$ export AWS_REGION=us-west-2
(venv) ubuntu@ip-172-31-26-191:~$ export TABLE_NAME=arxiv-papers
(venv) ubuntu@ip-172-31-26-191:~$ pkill -f api_server.py || true
(venv) ubuntu@ip-172-31-26-191:~$ nohup python3 api_server.py 8080 > server.log 2>&1 &
[1] 4769
(venv) ubuntu@ip-172-31-26-191:~$ curl "http://localhost:8080/papers/recent?category=cs.LG&limit=1"
{"category": "cs.LG", "papers": [{"arxiv_id": "0110036v1", "title": "Efficient algorithms for decision tree cross-validation", "authors": ["Hendrik Blockeel", "Jan Struyf"], "published": "2001-10-17T15:45:23Z", "categories": ["cs.LG", "I.2.6"]}], "count": 1}(venv) ubuntu@ipcurl "http://localhost:8080/papers/recent?category=cs.LG&limit=3"ory=cs.LG&limit=3"
{"category": "cs.LG", "papers": [{"arxiv_id": "0110036v1", "title": "Efficient algorithms for decision tree cross-validation", "authors": ["Hendrik Blockeel", "Jan Struyf"], "published": "2001-10-17T15:45:23Z", "categories": ["cs.LG", "I.2.6"]}, {"arxiv_id": "0103003v1", "title": "Learning Policies with External Memory", "authors": ["Leonid Peshkin", "Nicolas Meuleau", "Leslie Kaelbling"], "published": "2001-03-02T01:55:46Z", "categories": ["cs.LG", "I.2.8;I.2.6;I.2.11;I.2;I.2.3"]}, {"arxiv_id": "0011044v1", "title": "Scaling Up Inductive Logic Programming by Learning from Interpretations", "authors": ["Hendrik Blockeel", "Luc De Raedt", "Nico Jacobs", "Bart Demoen"], "published": "2000-11-29T12:14:50Z", "categories": ["cs.LG", "I.2.6 ; I.2.3"]}], "count": 3}(venv) ubuntu@ip-172-31-26-191:~$
(venv) ubuntu@ip-172-31-26-191:~$ curl "http://localhost:8080/papers/author/hendrik%20blockeel"
{"author": "hendrik%20blockeel", "papers": [], "count": 0}(venv) ubuntu@ip-172-31-26-191:~$
(venv) ubuntu@ip-172-31-26-191:~$ curl "http://localhost:8080/papers/0110036v1"
{"categories": ["cs.LG", "I.2.6"], "PK": "PAPER#0110036v1", "authors": ["Hendrik Blockeel", "Jan Struyf"], "arxiv_id": "0110036v1", "GSI2SK": "2001-10-17", "published": "2001-10-17T15:45:23Z", "abstract": "Cross-validation is a useful and generally applicable technique often\nemployed in machine learning, including decision tree induction. An important\ndisadvantage of straightforward implementation of the technique is its\ncomputational overhead. In this paper we show that, for decision trees, the\ncomputational overhead of cross-validation can be reduced significantly by\nintegrating the cross-validation with the normal decision tree induction\nprocess. We discuss how existing decision tree algorithms can be adapted to\nthis aim, and provide an analysis of the speedups these adaptations may yield.\nThe analysis is supported by experimental results.", "GSI2PK": "PAPER#0110036v1", "title": "Efficient algorithms for decision tree cross-validation"(venv) ubuntu@ip-172-31-26-191:~$ curl "http://localhost:8080/papers/search?category=cs.LG&start=2001-10-01&end=2001-10-31"&end=2001-10-31"
{"error": "not found"}(venv) ubuntu@ip-172-31-26-191:~$
(venv) ubuntu@ip-172-31-26-191:~$ curl "http://localhost:8080/papers/keyword/efficient?limit=5"
{"keyword": "efficient", "papers": [], "count": 0}(venv) ubuntu@ip-172-31-26-191:~$
