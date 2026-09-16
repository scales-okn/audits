import sys
import json

import paramiko
import requests
import pandas as pd
from io import StringIO
from sshtunnel import SSHTunnelForwarder

import qc_constants
from qc_constants import fuseki_hostname, fuseki_username, fuseki_port



_process_sparql = lambda response: [{k: v['value'] for k,v in row.items()} for row in response['results']['bindings']]

use_live_fuseki = False # whether to pull results from the fuseki server on the graph-database vm, rather than the frozen result csvs
skip_write = False
outpath = 'results.json'



def get_question_results(question_num, is_first_of_run=True, verbose=True, serialize_dfs=False):
    query_num = qc_constants.question_queries[question_num]
    text = qc_constants.question_texts[question_num]

    if verbose and is_first_of_run:
        print(qc_constants.filters_description, '\n')
    print(f'Retrieving results for question {question_num}...')
    if verbose:
        if 'Clayton' in text and use_live_fuseki:
            print('n.b. due to the size of the Clayton test set, this query may run slowly (i.e. ~20s)')
        print(f'Question text: "{text}"\n')

    # pull query file from remote
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=fuseki_hostname, username=fuseki_username)
    sftp = ssh.open_sftp()
    query = sftp.open(f"qc_results/qc_query_{query_num}.sparql", "r").read().decode("utf-8")
    if not use_live_fuseki:
        csv = sftp.open(f"qc_results/qc_query_{query_num}_results.csv", "r").read().decode("utf-8")
        sparql_results = pd.read_csv(StringIO(csv)).to_dict('records')
    sftp.close()
    ssh.close()

    # submit query to fuseki server on remote
    if use_live_fuseki:
        port = qc_constants.fuseki_port
        with SSHTunnelForwarder((fuseki_hostname, 22), ssh_username=fuseki_username,
            remote_bind_address=("127.0.0.1", fuseki_port), local_bind_address=("127.0.0.1", fuseki_port)) as tunnel:
            response = requests.get(f"http://127.0.0.1:{fuseki_port}/scales-kg/sparql", params={"query": query}, headers={"Accept": "application/sparql-results+json"})
            response.raise_for_status()
            sparql_results = _process_sparql(response.json())

    # format answer
    if question_num not in qc_constants.question_helpers:
        raise Exception(f'Question {question_num} has not yet been implemented')
    answer = qc_constants.question_helpers[question_num](sparql_results)
    if verbose:
        if type(answer) in (int, float):
            print(f'Answer: {answer}')
        else:
            answer_printable = str(answer.to_dict('records') if type(answer) == pd.DataFrame else answer)
            print(f'Answer is {type(answer)} with length {len(answer)}')
            print(answer_printable[:100], '(continues)\n' if len(answer_printable) > 100 else '\n')
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
