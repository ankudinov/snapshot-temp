#!/usr/bin/env python3

import yaml
import pyeapi
from time import time as time                   # used in: time_stamp()
from datetime import datetime as datetime       # used in: time_stamp()

config_file = './snapshot-cfg.yaml'


def time_stamp():
    """
    time_stamp function can be used for debugging or to display timestamp for specific event to a user
    :return: returns current system time as a string in Y-M-D H-M-S format
    """
    time_not_formatted = time()
    time_formatted = datetime.fromtimestamp(time_not_formatted).strftime('%Y-%m-%d:%H:%M:%S.%f')
    return time_formatted


def merge_dict(d1, d2):
    """
    Merge 2 dictionaries together, keeping every element with unique key sequence.
    Relies on recursion.
    :param d1: Primary dictionary.
    :param d2: Secondary dictionary. If element is already present in d1, conflicting element from d2 will be discarded.
    :return: Combined dictionary. All elements from d1 and elements from d2 if missing in d1.
    """
    result = dict()
    all_keys = set(d1.keys()).union(d2.keys())
    for key in all_keys:
        if key not in d1.keys():
            result[key] = d2[key]
        elif key not in d2.keys():
            result[key] = d1[key]
        else:
            if isinstance(d1[key], dict) and isinstance(d2[key], dict):
                    result[key] = merge_dict(d1[key], d2[key])  # recursion
            else:
                if d1[key] == 'to be defined':
                    result[key] = d2[key]
                else:
                    result[key] = d1[key]

    return result


def build_snapshot_job(yaml_file):

    try:
        file = open(yaml_file, mode='r')
    except Exception as _:
        print('ERROR: Can not open task file.')
        raise SystemExit(0)
    else:
        yaml_data = yaml.load(file)
        file.close()

    snapshot_dict = dict()

    for block in yaml_data:
        if 'host_db' in block.keys():
            for entry in block['host_db']:
                for host in entry.keys():
                    snapshot_dict = merge_dict(snapshot_dict, {
                        host: {
                            'tags': set(entry[host]),
                            'commands': []
                        }
                    })

    for block in yaml_data:
        if 'snapshot_commands' in block.keys():
            command_tags = set(block['tags'])
            for host in snapshot_dict.keys():
                host_tags = snapshot_dict[host]['tags']
                if command_tags.issubset(host_tags):
                    for command in block['snapshot_commands']:
                        snapshot_dict[host]['commands'].append(command)

    for block in yaml_data:
        if 'username' in block.keys():
            user_tags = set(block['tags'])
            for host in snapshot_dict.keys():
                host_tags = snapshot_dict[host]['tags']
                if user_tags.issubset(host_tags):
                    snapshot_dict[host] = merge_dict(snapshot_dict[host], {
                        'username': block['username'],
                        'password': block['password'],
                    })

    return snapshot_dict


if __name__ == '__main__':
    snapshot_job = build_snapshot_job(config_file)

    result_list = list()

    for ip in snapshot_job:
        conn = pyeapi.connect(host=ip, transport='https', username=snapshot_job[ip]['username'], password=snapshot_job[ip]['password'])
        try:
            results = conn.execute(snapshot_job[ip]['commands'], encoding='text')['result']
        except Exception as e:
            print('ERROR: Failed to execute command on %s.' % ip)
            print(e)
        else:
            zip_results = zip(snapshot_job[ip]['commands'], results)
            for command, result in zip_results:
                result_list.append({
                    'ip': ip,
                    'command': command,
                    'result': result['output']
                })

    try:
        timestamp = str(time_stamp())
        filename = 'snapshot' + timestamp + '.txt'
        file = open(filename, mode='w')
    except Exception as _:
        print('ERROR: Can not create ', filename)
    else:
        ip_set = set([entry['ip'] for entry in result_list])
        for ip in ip_set:
            file.write('#' * 40 + '\n')
            file.write('### SNAPSHOT: %s' % ip + '\n')
            file.write('### TIMESTAMP: %s' % timestamp + '\n')
            file.write('#' * 40 + '\n')
            for snapshot in result_list:
                if snapshot['ip'] == ip:
                    file.write('~-' * 20 + '\n')
                    file.write('### COMMAND: %s' % snapshot['command'] + '\n')
                    file.write('~-' * 20 + '\n')
                    file.write('### RESULT:' + '\n')
                    file.write('~-' * 20 + '\n')
                    file.write(snapshot['result'] + '\n')
        file.close()
