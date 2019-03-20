from flask import Flask, request
from requests_futures.sessions import FuturesSession
from clear_entries import *
import subprocess
import json
import os
import time
import sys

app = Flask(__name__)

# Port and hostname of the port of the workload generation pods
workload_port = int(os.environ['WORKLOAD_PORT'])
workload_hostnames = os.environ['WORKLOAD_HOSTNAME']

# Return an in-order list of hostnames
def parse_hostnames():
    hostname_list = workload_hostnames.split(',')
    return hostname_list
    
# Asyncrnously run command
@app.route('/startab')
def run_experiment():
    workload_pods = int(request.args.get('w', default=1))
    n = int(request.args.get('n', default=350))
    c = int(request.args.get('c', default=150))
    frontend_hostname = request.args.get('hostname')
    frontend_port = int(request.args.get('port', default=80))

    session = FuturesSession()
    
    hostname_list = parse_hostnames()
    futures = []
    for worker_id in range(workload_pods):
        port = workload_port + worker_id

        complete_hostname = 'http://' + hostname_list[worker_id] + ':' + str(port) + '/startab'
        print("hostname is {}".format(complete_hostname))
        futures.append(session.get(complete_hostname, params={'n': n,
                                                'c': c,
                                                'hostname': frontend_hostname,
                                                'port': frontend_port
        }))

    for future in futures:
        print(future.result())
    sys.stdout.flush()
    return 'Experiment started!'

# Collect and clear results
@app.route('/collectresults')
def collect_results():
    workload_pods = int(request.args.get('w', default=1))
    hostname_list = parse_hostnames()
    
    session = FuturesSession()
    futures = []
    for worker_id in range(workload_pods):
        port = workload_port + worker_id
        complete_hostname = 'http://' + hostname_list[worker_id] + ':' + str(port) + '/collectresults'
        futures.append(session.get(complete_hostname))

    results = []
    for future in futures:
        result = future.result()
        print(type(result))
        sys.stdout.flush()
        results.append(result.json())

    print(results)
    sys.stdout.flush()
        
    return json.dumps(results)

@app.route('/clearentries')
def clear_results():
    hostname = request.args.get('hostname')
    deleted_successfully = delete_final(hostname)
    if deleted_successfully:
        return 'success'
    else:
        print('Still some remaining entries after 100 seconds of waiting')
        return 'fail'
    
def execute_parse_results():
    rps_cmd = 'cat /app/output.txt | grep \'Requests per second\' | awk {{\'print $4\'}}'
    latency90_cmd = 'cat /app/output.txt | grep \'90%\' | awk {\'print $2\'}'
    latency50_cmd = 'cat /app/output.txt | grep \'50%\' | awk {\'print $2\'}'
    latency99_cmd = 'cat /app/output.txt | grep \'99%\' | awk {\'print $2\'}'
    latency100_cmd = 'cat /app/output.txt | grep \'Time per request\' | awk \'NR==1{{print $4}}\''

    results = {}

    proc_rps = subprocess.Popen(rps_cmd, shell=True, stdout=subprocess.PIPE)
    proc_latency90 = subprocess.Popen(latency90_cmd, shell=True, stdout=subprocess.PIPE)
    proc_latency50 = subprocess.Popen(latency50_cmd, shell=True, stdout=subprocess.PIPE)
    proc_latency99 = subprocess.Popen(latency99_cmd, shell=True, stdout=subprocess.PIPE)
    proc_latency100 = subprocess.Popen(latency100_cmd, shell=True, stdout=subprocess.PIPE)

    result_rps = proc_rps.stdout.read().decode()
    result_latency90 = proc_latency90.stdout.read().decode()
    result_latency50 = proc_latency50.stdout.read().decode()
    result_latency99 = proc_latency99.stdout.read().decode()
    result_latency100 = proc_latency100.stdout.read().decode()

    try:
        results['rps'] = float(result_rps.strip('\n'))
        results['latency99'] = float(result_latency99.strip('\n'))
        results['latency90'] = float(result_latency90.strip('\n'))
        results['latency50'] = float(result_latency50.strip('\n'))
        results['latency100'] = float(result_latency100.strip('\n'))
    except:
        if len(results.keys()) == 0:
            return {}
    
    return results

if __name__ == '__main__':
    app.run(
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 80)
    )
