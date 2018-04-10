import os
from pymongo import MongoClient


def get_db_client():

    client = None

    if __is_hostname_reachable('db'):
        client = MongoClient('mongodb://bolao_user:bolao_pass@db:27017/admin')
    else:
        # if dev environment
        client = MongoClient()

    return client


def __is_hostname_reachable(hostname):
    import subprocess

    try:
        if os.name == 'nt':
            cmd = ['ping', hostname, '-n', '1']
        else:
            cmd = ['ping', '-c', '1', hostname]

        with open(os.devnull, 'w') as DEVNULL:
            response = subprocess.check_call(cmd,
                 stdout=DEVNULL,  # suppress output
                 stderr=DEVNULL
            )
        return True
    except subprocess.CalledProcessError:
        return False


