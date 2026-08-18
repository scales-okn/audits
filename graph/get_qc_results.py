import sys
import json

import paramiko
import requests
import pandas as pd
from sshtunnel import SSHTunnelForwarder

import qc_constants
from qc_constants import fuseki_hostname, fuseki_username, fuseki_port

outpath = 'results.json'
skip_write = False



def get_question_results(question_num, is_first_of_run=True, verbose=True, serialize_dfs=False):
    query_num = qc_constants.question_queries[question_num]
    text = qc_constants.question_texts[question_num]
    if type(text) != str: # i.e. lambda that pulls specific val from query
        text = text(query)

    if verbose and is_first_of_run:
        print(qc_constants.filters_description, '\n')
    print(f'Retrieving results for question {question_num}...')
    if verbose:
        if 'Clayton' in text:
            print('n.b. Clayton queries may run slowly (i.e. ~20s) on this test set')
        print(f'Question text: "{text}"')

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

    # # debug block
    # results = sparql_results['results']['bindings']
    # print(f'\n{len(results)} results')
    # x = 10 if len(results) > 10 else len(results)
    # for row in results[:x]:
    #     print(row)
    # print()

    # format answer
    if question_num not in qc_constants.question_helpers:
        raise Exception(f'Question {question_num} has not yet been implemented')
    answer = qc_constants.question_helpers[question_num](sparql_results['results']['bindings'])
    if verbose:
        if type(answer) in (int, float):
            print(f'Answer: {answer}')
        else:
            print(f'Answer is {type(answer)} with length {len(answer)}')
    if type(answer) == pd.DataFrame and serialize_dfs:
        answer = answer.to_dict('records')

    # return results
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
    for i,num in enumerate(question_nums):
        results[num] = get_question_results(num, is_first_of_run=(i==0),
            verbose=verbose, serialize_dfs=serialize_dfs)
    return results

def get_question_results_all(verbose=True, serialize_dfs=False):
    return get_question_results_multiple(
        qc_constants.question_helpers.keys(), verbose=verbose, serialize_dfs=serialize_dfs)



if __name__ == "__main__":
    print()
    if len(sys.argv)==1:
        results = get_question_results_all(serialize_dfs=True)
    else:
        results = get_question_results_multiple([int(x) for x in sys.argv[1:]], serialize_dfs=True)

    if not skip_write:
        with open(outpath, 'w') as f:
            json.dump(results, f)
        print(f'Wrote results to {outpath}')
    print('Script complete\n\n')
