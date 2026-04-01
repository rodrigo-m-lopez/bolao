import os
import logging
from pymongo import MongoClient

logger = logging.getLogger(__name__)


def get_db_client():
    """Return a MongoClient.

    Em produção (Docker), conecta ao serviço 'db' com credenciais do ambiente.
    Em desenvolvimento (incluindo DEV_MOCK_AUTH), conecta ao MongoDB local (localhost).
    DEV_MOCK_AUTH controla apenas a autenticação OAuth, não o banco de dados.
    """
    if __is_hostname_reachable('db'):
        user = os.environ.get('MONGO_USER', 'bolao_user')
        password = os.environ.get('MONGO_PASS', 'bolao_pass')
        auth_db = os.environ.get('MONGO_AUTH_DB', 'admin')
        uri = 'mongodb://{}:{}@db:27017/{}'.format(user, password, auth_db)
        logger.info('Conectando ao MongoDB em db:27017')
        return MongoClient(uri)
    else:
        logger.info('Host "db" inalcancavel, usando MongoDB local (dev)')
        return MongoClient()


def __is_hostname_reachable(hostname):
    import subprocess

    try:
        if os.name == 'nt':
            cmd = ['ping', hostname, '-n', '1']
        else:
            cmd = ['ping', '-c', '1', hostname]

        with open(os.devnull, 'w') as DEVNULL:
            subprocess.check_call(cmd, stdout=DEVNULL, stderr=DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False
