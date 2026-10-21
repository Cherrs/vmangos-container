"""Pinned-source VMaNGOS container startup and one-shot, fresh-database bootstrap."""
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path('/opt/vmangos')
DATABASES = {'logon': 'realmd', 'characters': 'characters', 'world': 'mangos', 'logs': 'logs'}


def revision():
    return (ROOT / 'REVISION').read_text().strip()


def sql(query=None, database=None, file=None, root=False):
    env = os.environ.copy()
    env['MYSQL_PWD'] = env['DB_ROOT_PASSWORD' if root else 'DB_PASSWORD']
    args = ['mariadb', '--protocol=TCP', '-h', env.get('DB_HOST', 'vmangos-db'),
            '-P', env.get('DB_PORT', '3306'), '-u', 'root' if root else 'mangos',
            '--connect-timeout=5', '--default-character-set=utf8', '--max-allowed-packet=256M', '-N', '-B']
    if database:
        args.append(database)
    if file:
        with Path(file).open('rb') as stream:
            result = subprocess.run(args, stdin=stream, env=env, capture_output=True)
    else:
        result = subprocess.run(args, input=query.encode(), env=env, capture_output=True)
    if result.returncode:
        # Credentials are never included in arguments or diagnostic output.
        message = result.stderr.decode(errors='replace').strip()
        for key in ('DB_PASSWORD', 'DB_ROOT_PASSWORD'):
            if env.get(key):
                message = message.replace(env[key], '<redacted>')
        raise RuntimeError(message)
    return result.stdout.decode().strip()


def ready(root=False):
    if root:
        return sql('SELECT 1;', root=True) == '1'
    return sql("SELECT revision FROM realmd._k3s_bootstrap WHERE id=1 AND status='ready';") == revision()


def wait(root=False):
    for attempt in range(240):
        try:
            if ready(root):
                return
        except RuntimeError:
            pass
        if attempt % 12 == 0:
            print('Waiting for database' if root else 'Waiting for matching database bootstrap', flush=True)
        time.sleep(5)
    raise RuntimeError('Database/bootstrap was not ready after 20 minutes; inspect the bootstrap Job logs.')


def render(text, overrides):
    for key, value in overrides.items():
        pattern = r'^' + re.escape(key) + r'\s*=.*$'
        if not re.search(pattern, text, re.M):
            raise ValueError(f'Unknown upstream config key: {key}')
        text = re.sub(pattern, lambda _: f'{key} = {value}', text, flags=re.M)
    return text


def conf(mode):
    password = os.environ['DB_PASSWORD']
    if not re.fullmatch(r'[A-Za-z0-9_]{24,128}', password):
        raise ValueError('DB_PASSWORD must contain 24-128 ASCII letters, digits or underscores.')
    host = os.environ.get('DB_HOST', 'vmangos-db')
    if not re.fullmatch(r'[A-Za-z0-9.-]+', host):
        raise ValueError('Invalid DB_HOST')
    port = int(os.environ.get('DB_PORT', '3306'))
    conn = lambda db: f'"{host};{port};mangos;{password};{db}"'
    overrides = {'BindIP': '"0.0.0.0"', 'LogsDir': '"/var/log/vmangos/"',
                 'PidFile': '""', 'LogLevel.Console': '2', 'WaitAtStartupError': '0'}
    if mode == 'realmd':
        overrides.update({'LoginDatabaseInfo': conn('realmd'), 'RealmServerPort': '3724'})
    else:
        for key, db in [('Login', 'realmd'), ('World', 'mangos'), ('Character', 'characters'), ('Logs', 'logs')]:
            overrides[f'{key}Database.Info'] = conn(db)
        overrides.update({'RealmID': '1', 'DataDir': '"/data"', 'WorldServerPort': '8085',
                          'Console.Enable': '1', 'Ra.Enable': '0', 'SOAP.Enabled': '0',
                          'Terrain.Preload.Continents': '0', 'Terrain.Preload.Instances': '0'})
    text = (ROOT / 'etc' / f'{mode}.conf.dist').read_text()
    target = Path('/run/vmangos') / f'{mode}.conf'
    target.write_text(render(text, overrides))
    target.chmod(0o600)
    return target


def bootstrap():
    password = os.environ['DB_PASSWORD']
    address = os.environ['PUBLIC_ADDRESS']
    name = os.environ.get('REALM_NAME', 'VMaNGOS')
    if not re.fullmatch(r'[A-Za-z0-9_]{24,128}', password):
        raise ValueError('DB_PASSWORD must contain 24-128 ASCII letters, digits or underscores.')
    if not re.fullmatch(r'[A-Za-z0-9.-]{1,32}', address):
        raise ValueError('PUBLIC_ADDRESS must be an IPv4 address or DNS name of at most 32 characters.')
    if not re.fullmatch(r'[A-Za-z0-9 _-]{1,32}', name):
        raise ValueError('REALM_NAME must contain 1-32 ASCII letters, digits, spaces, underscores or hyphens.')
    wait(root=True)
    count = int(sql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN "
                    "('realmd','characters','mangos','logs');", root=True))
    if count:
        try:
            state = sql('SELECT status,revision FROM realmd._k3s_bootstrap WHERE id=1;', root=True)
        except RuntimeError:
            state = ''
        if state == f'ready\t{revision()}':
            print('This revision is already initialized; no data or realm settings changed.')
            return
        raise RuntimeError('Existing or partially imported database found. Refusing to re-import. '
                           'Inspect/restore it manually; this bootstrap is for fresh databases only.')
    for db in DATABASES.values():
        sql(f'CREATE DATABASE IF NOT EXISTS {db} DEFAULT CHARSET utf8 COLLATE utf8_general_ci;', root=True)
    sql("CREATE TABLE realmd._k3s_bootstrap (id INT PRIMARY KEY, status VARCHAR(16), revision CHAR(40));"
        f"INSERT INTO realmd._k3s_bootstrap VALUES (1,'importing','{revision()}');", root=True)
    sql(f"CREATE USER IF NOT EXISTS 'mangos'@'%' IDENTIFIED BY '{password}';"
        f"ALTER USER 'mangos'@'%' IDENTIFIED BY '{password}';", root=True)
    for db in DATABASES.values():
        sql(f"GRANT ALL PRIVILEGES ON {db}.* TO 'mangos'@'%';", root=True)
    for source, db in DATABASES.items():
        filename = 'mangos' if source == 'world' else source
        print(f'Importing {db}', flush=True)
        sql(database=db, file=ROOT / 'db' / 'mysql-dump' / f'{filename}.sql', root=True)
    # The native core checks these IDs but does not execute missing migrations.
    applied = {kind: set(sql('SELECT id FROM migrations;', database=db, root=True).splitlines())
               for kind, db in DATABASES.items()}
    for file in sorted((ROOT / 'sql' / 'migrations').glob('*.sql')):
        match = re.fullmatch(r'(\d+)_(logon|characters|world|logs)\.sql', file.name)
        if not match:
            raise RuntimeError(f'Unexpected migration name: {file.name}')
        mid, kind = match.groups()
        if mid not in applied[kind]:
            print(f'Applying {file.name}', flush=True)
            sql(database=DATABASES[kind], file=file, root=True)
    # Both addresses are public so local subnet detection cannot return a Pod IP.
    sql("DELETE FROM realmd.realmlist WHERE id <> 1;"
        "INSERT INTO realmd.realmlist (id,name,address,localAddress,localSubnetMask,port,icon,realmflags,timezone,"
        "allowedSecurityLevel,population,gamebuild_min,gamebuild_max,flag,realmbuilds) "
        f"VALUES (1,'{name}','{address}','{address}','255.255.255.255',8085,1,2,1,0,0,5875,5875,2,'5875') "
        f"ON DUPLICATE KEY UPDATE name='{name}',address='{address}',localAddress='{address}',"
        "localSubnetMask='255.255.255.255',port=8085,realmbuilds='5875';", root=True)
    for kind, db in DATABASES.items():
        current = set(sql('SELECT id FROM migrations;', database=db, root=True).splitlines())
        required = {f.name.split('_')[0] for f in (ROOT / 'sql' / 'migrations').glob(f'*_{kind}.sql')}
        if required - current:
            raise RuntimeError(f'{db}: missing migrations after import')
    sql("UPDATE realmd._k3s_bootstrap SET status='ready' WHERE id=1;", root=True)
    print('Bootstrap complete. No player or GM account was created.')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'mangosd'
    if mode == 'bootstrap':
        bootstrap()
    elif mode == 'wait':
        wait()
    elif mode in ('realmd', 'mangosd'):
        wait()
        if mode == 'mangosd':
            for folder in ('5875/dbc', 'maps', 'vmaps', 'mmaps'):
                path = Path('/data') / folder
                if not path.is_dir() or not any(path.iterdir()):
                    raise RuntimeError(f'Missing or empty client data directory: {path}')
        config = conf(mode)
        os.execv(str(ROOT / 'bin' / mode), [mode, '-c', str(config)])
    else:
        raise ValueError(f'Unknown command: {mode}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
