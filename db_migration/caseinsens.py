#!/usr/bin/env python3

# Username case collision pruning script
#
# This script is meant to remove accidentally-made accounts from an
# OpenFusion server database, so it can be updated from version 3 to 4.
# 
# Start by running your server and making sure it tells you to run this
# script. If it does, execute this script in a command line using a Python
# interpreter, passing the filename of your DB as the only argument.
#
# The script will create a backup of your DB, as well as a log file
# containing a record of all the changes that were made. Make sure to
# preserve this log file in case you need to reference it in the future.
#
# If something goes wrong with the first invocation, you'll need to move the
# DB backup and log files out of the way before the script can be re-run.
#
# If all goes well, you should be able to re-run your OF server and it'll
# complete the migration to DB version 4.
#
# Do not hesitate to ask the OF developers for assistance if necessary.

import sys
import os.path
import shutil
import logging
from functools import reduce

import sqlite3

LOGFILE = 'caseinsens.log'
DELETION_TRESHOLD = 2
DRY_RUN = False # set to True if testing the script

def check_version(cur):
    cur.execute("SELECT Value FROM Meta WHERE Key = 'DatabaseVersion';")
    ver = cur.fetchone()[0]

    if ver < 3:
        sys.exit('fatal: you must first upgrade your DB version to 3 by running the server on it')
    elif ver >= 4:
        sys.exit('fatal: your database is already version {}. this script is meant to clean up version 3 before it can be upgrated to 4.'.format(ver))

def get_logins(cur):
    cur.execute('SELECT Login FROM Accounts GROUP BY LOWER(Login) HAVING COUNT(*) > 1;')
    return [x[0] for x in cur.fetchall()]

def rate_triviality(cur, accid, accname):
    cur.execute('SELECT PlayerID, TutorialFlag, Level FROM Players WHERE AccountID = ?;', (accid,))
    players = cur.fetchall()

    # are there zero player characters?
    if len(players) == 0:
        logging.info('** {} has no players'.format(accname))
        return 0, 0

    # is the only player still in the tutorial?
    if len(players) == 1 and players[0][1] == 0:
        logging.info('** {} is in tutorial'.format(accname))
        return 1, 0
    
    # is the only player still level 1?
    if len(players) == 1 and players[0][2] == 1:
        logging.info('** {} is level 1'.format(accname))
        return 2, 1

    # sum player levels as a heuristic of effort expended on account
    levelsum = reduce(lambda a, b: a+b, map(lambda x: x[2], players))

    logging.info('** {} is non-trivial'.format(accname))
    return (99, levelsum)

def process_login(cur, login):
    cur.execute('SELECT Login, AccountID FROM Accounts WHERE Login LIKE ?;', (login,))
    duplicates = cur.fetchall()

    rest = []
    for name, accid in duplicates:
        rating, levelsum = rate_triviality(cur, accid, name)

        if rating < DELETION_TRESHOLD:
            logging.info('* triviality for {} is {}; deleting'.format(name, rating))
            if not DRY_RUN:
                cur.execute('DELETE FROM Accounts WHERE AccountID = ?;', (accid,))
        else:
            logging.info('* triviality for {} is {}, levelsum = {}; keeping'.format(name, rating, levelsum))
            rest.append((levelsum, name, accid, ))

    if len(rest) == 0:
        logging.warning('all variants of {} were trivial?'.format(login))
        return

    # pick the account with the largest sum of character levels as primary...
    rest.sort()
    rest.reverse()
    logging.info('{} looks like the primary'.format(rest[0][1]))
    rest = rest[1:]

    # ...and then rename the rest
    for i in range(len(rest)):
        oldname = rest[i][1]
        accid = rest[i][2]
        prefix = '_' * (i+1)
        newname = prefix + oldname

        # mind the 32 character limit
        if len(newname) > 32:
            newname = newname[:32]

        logging.info('* renaming {} to {}'.format(oldname, newname))
        if not DRY_RUN:
            cur.execute('UPDATE Accounts SET Login = ? WHERE AccountID = ?;', (newname, accid))

def main(path):
    if os.path.isfile(LOGFILE):
        sys.exit('fatal: a log file named {} already exists. refusing to modify.'.format(LOGFILE))

    logging.basicConfig(filename=LOGFILE, level=20, format='%(levelname)s: %(message)s')

    if not os.path.isfile(path):
        sys.exit('fatal: {} is not a file'.format(path))

    bakpath = path + '.caseinsens.bak'

    if os.path.isfile(bakpath):
        sys.exit('fatal: a DB backup named {} already exists. refusing to overwrite.'.format(bakpath))

    shutil.copy(path, bakpath)
    logging.info('saved database backup to {}'.format(bakpath))
    print('saved database backup to {}'.format(bakpath))

    with sqlite3.connect(path) as db:
        cur = db.cursor()

        check_version(cur)

        logins = get_logins(cur)

        for login in logins:
            process_login(cur, login)

    logging.info('done.')
    print('done.')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: {} database.db'.format(sys.argv[0]))
    main(sys.argv[1])
