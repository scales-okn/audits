'''
These QC results were generated from a small test dataset filtered down
from the full dataset according to the following criteria:

- apd: arrests whose NC.ActivityDate is between Jan–Mar 2015 inclusive
- clayton: cases for which the year part of the case id is "82"
- fulton: charges whose NC.StartDate is in Jan 2021
- pacer: cases in Alaska district court (akd)
'''

import sys
import json

import requests
import pandas as pd
from sshtunnel import SSHTunnelForwarder
import paramiko # for compatibility with sshtunnel, use <4.0 when installing

import qc_constants
from qc_constants import fuseki_hostname, fuseki_username, fuseki_port

outpath = 'results.json'
skip_write = False



def get_question_results(question_num, verbose=True, serialize_dfs=False):
    question_num = int(question_num)
    query_num = qc_constants.question_queries[question_num]
    print(f'Retrieving results for question {question_num}...')

    # pull query file from remote
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=fuseki_hostname, username=fuseki_username)
    sftp = ssh.open_sftp()
    with sftp.open(
        f"qc_results/qc_query_{query_num}.sparql", "r") as f:
        query = f.read().decode("utf-8")
    sftp.close()
    ssh.close()

    # submit query to fuseki server on remote
    port = qc_constants.fuseki_port
    with SSHTunnelForwarder(
        (fuseki_hostname, 22), ssh_username=fuseki_username,
        remote_bind_address=("127.0.0.1", fuseki_port),
        local_bind_address=("127.0.0.1", fuseki_port)) as tunnel:
        response = requests.get(
            f"http://127.0.0.1:{fuseki_port}/scales-kg/sparql",
            params={"query": query},
            headers={"Accept": "application/sparql-results+json"})
        response.raise_for_status()
        sparql_results = response.json()

    # format results
    answer = qc_constants.question_helpers[question_num](sparql_results['results']['bindings'])
    if type(answer) == pd.DataFrame and serialize_dfs:
        answer = answer.to_dict('records')
    text = qc_constants.question_texts[question_num]
    if type(text) != str: # i.e. lambda that pulls specific val from query
        text = text(query)

    # return results
    if verbose:
        if type(answer) in (pd.DataFrame, list):
            print(f'Answer is DataFrame with {len(answer)} rows')
        else:
            print(f'Answer: {answer}')
    results = {
        'question_text': text,
        'question_answer': answer,
        'sparql_query': query,
        'sparql_results': sparql_results
    }
    print('...Done\n')
    return results



def get_question_results_multiple(question_nums, verbose=True, serialize_dfs=False):
    results = {}
    for num in question_nums:
        results[num] = get_question_results(num, verbose=verbose, serialize_dfs=serialize_dfs)
    return results

def get_question_results_all(verbose=True, serialize_dfs=False):
    return get_question_results_multiple(
        qc_constants.question_texts.keys(), verbose=verbose, serialize_dfs=serialize_dfs)



if __name__ == "__main__":
    print()
    if len(sys.argv)==1:
        results = get_question_results_all(serialize_dfs=True)
    else:
        results = get_question_results_multiple(sys.argv[1:])

    if not skip_write:
        with open(outpath, 'w') as f:
            json.dump(results, f)
        print(f'Wrote results to {outpath}')
    print('Script complete\n')
