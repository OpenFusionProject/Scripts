#!/usr/bin/env python3

# OG racing score conversion script
#
# This script is meant to update racing scoreboards from Retro-style scores
# to OG-accurate scores. Be careful to only run this once!
#
# The script will create a backup of your DB, as well as a log file
# containing a record of all the changes that were made. Make sure to
# preserve this log file in case you need to reference it in the future.
#
# If something goes wrong with the first invocation, you'll need to move the
# DB backup and log files out of the way before the script can be re-run.
#
# If all goes well, you should see different, OG-true scores in IZ scoreboards.
#
# Do not hesitate to ask the OF developers for assistance if necessary.

import sys
import os.path
import shutil
import logging
import json
from math import exp

import sqlite3

LOGFILE = 'ogracing.log'
DRY_RUN = False # set to True if testing the script
CAP_SCORES = True # set to False to disable capping scores to the IZ maximum

class EpData:
    max_score = 0
    pod_factor = 0
    max_pods = 0
    max_time = 0
    time_factor = 0
    scale_factor = 0

class RaceResult:
    epid = 0
    playerid = 0
    score = 0
    timestamp = 0
    ring_count = 0
    time = 0

def check_version(cur):
    cur.execute("SELECT Value FROM Meta WHERE Key = 'DatabaseVersion';")
    ver = cur.fetchone()[0]

    if ver < 2:
        sys.exit('fatal: you must first upgrade your DB version to 2 by running the server at least once')

def load_epinfo():
    epinfo = {}
    with open("drops.json", "r") as f:
        dat = json.load(f)["Racing"]
    for key in dat:
        val = dat[key]
        epdata = EpData()
        epid = int(val["EPID"])
        epdata.max_score = int(val["ScoreCap"])
        epdata.pod_factor = float(val["PodFactor"])
        epdata.max_pods = int(val["TotalPods"])
        epdata.max_time = int(val["TimeLimit"])
        epdata.time_factor = float(val["TimeFactor"])
        epdata.scale_factor = float(val["ScaleFactor"])
        epinfo[epid] = epdata
    return epinfo
    

def get_results(cur):
    results = []
    cur.execute('SELECT EPID, PlayerID, Timestamp, RingCount, Time, Score FROM RaceResults;')
    for x in cur.fetchall():
        result = RaceResult()
        result.epid = int(x[0])
        result.playerid = int(x[1])
        result.timestamp = int(x[2])
        result.ring_count = int(x[3])
        result.time = int(x[4])
        result.score = int(x[5])
        results.append(result)
    return results

def process_result(cur, result, epinfo):
    epdata = epinfo[result.epid]
    pod_score = (epdata.pod_factor * result.ring_count) / epdata.max_pods
    time_score = (epdata.time_factor * result.time) / epdata.max_time
    newscore = int(exp(pod_score - time_score + epdata.scale_factor))
    if CAP_SCORES and newscore > epdata.max_score:
        logging.warning('score {} greater than max ({}) for epid {}, capping'.format(newscore, epdata.max_score, result.epid))
        print('warning: score {} greater than max ({}) for epid {}, capping'.format(newscore, epdata.max_score, result.epid))
        newscore = epdata.max_score
    logging.info('* {} -> {} (EPID: {}, pods: {}, time: {})'.format(result.score, newscore, result.epid, result.ring_count, result.time))
    if not DRY_RUN:
        cur.execute('UPDATE RaceResults SET Score = ? WHERE (PlayerID, Timestamp) = (?, ?);', (newscore, result.playerid, result.timestamp))

def main(path):
    if os.path.isfile(LOGFILE):
        sys.exit('fatal: a log file named {} already exists. refusing to modify.'.format(LOGFILE))

    logging.basicConfig(filename=LOGFILE, level=20, format='%(levelname)s: %(message)s')

    if not os.path.isfile(path):
        sys.exit('fatal: {} is not a file'.format(path))

    bakpath = path + '.ogracing.bak'

    if os.path.isfile(bakpath):
        sys.exit('fatal: a DB backup named {} already exists. refusing to overwrite.'.format(bakpath))

    shutil.copy(path, bakpath)
    logging.info('saved database backup to {}'.format(bakpath))
    print('saved database backup to {}'.format(bakpath))

    epinfo = load_epinfo()

    with sqlite3.connect(path) as db:
        cur = db.cursor()

        check_version(cur)

        results = get_results(cur)

        for result in results:
            process_result(cur, result, epinfo)

    logging.info('done.')
    print('done.')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: {} database.db'.format(sys.argv[0]))
    main(sys.argv[1])
