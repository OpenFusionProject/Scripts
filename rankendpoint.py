# This script serves an HTTP endpoint that provides the racing scores.
#
# Example invocation for testing:
# $ RANKENDPOINT_DBPATH=/path/to/database.db RANKENDPOINT_ROUTE=/getranks flask --app rankendpoint.py run
#
# Example invocation in production (behind a properly configured gateway like nginx):
# $ RANKENDPOINT_DBPATH=/path/to/database.db RANKENDPOINT_ROUTE=/getranks uwsgi \
#     -s localhost:3031 --manage-script-name --mount /=rankendpoint:app --plugin python3

from flask import Flask, request
app = Flask(__name__)

import sqlite3
import sys
import os

header = "SUCCESS"

db_path = os.environ.get('RANKENDPOINT_DBPATH')
route = os.environ.get('RANKENDPOINT_ROUTE')

if None in (db_path, route):
    sys.exit('must set RANKENDPOINT_DBPATH and RANKENDPOINT_ROUTE environment variables')

# Opens database in read-only mode
# Checking same thread disabled for now, which is fine since we never modify anything
try:
    db = sqlite3.connect('file:{}?mode=ro'.format(db_path), uri=True, check_same_thread=False)
    cur = db.cursor()
except Exception as ex:
    print(ex)
    sys.exit()

#db.set_trace_callback(print)

def fetch_ranks(epid, date, num):
    sql = """
        SELECT
            PBRaceResults.PlayerID,
            Players.FirstName,
            Players.LastName,
            PBRaceResults.Score
        FROM (
            SELECT
                ROW_NUMBER() OVER (
                    PARTITION BY RaceResults.PlayerID
                    ORDER BY
                        RaceResults.Score DESC,
                        RaceResults.RingCount DESC,
                        RaceResults.Time ASC
                ) AS PersonalOrder,
                RaceResults.*
            FROM RaceResults
            WHERE EPID=? AND DATETIME(Timestamp, 'unixepoch') > DATETIME('now', ?)
        ) AS PBRaceResults
        INNER JOIN Players ON PBRaceResults.PlayerID=Players.PlayerID AND PBRaceResults.PersonalOrder=1
        ORDER BY
            PBRaceResults.Score DESC,
            PBRaceResults.RingCount DESC,
            PBRaceResults.Time ASC
        """

    if num > -1:
        sql += "LIMIT ?"
        args = (epid, date, num)
    else:
        args = (epid, date)

    cur = db.execute(sql + ";", args)
    rows = cur.fetchall()

    return rows

def fetch_my_ranks(pcuid, epid, date):
    sql = """
        SELECT
            RaceResults.PlayerID,
            Players.FirstName,
            Players.LastName,
            MAX(RaceResults.Score) AS MaxScore
        FROM RaceResults
        INNER JOIN Players ON RaceResults.PlayerID=Players.PlayerID
        WHERE RaceResults.PlayerID=? AND EPID=? AND DATETIME(Timestamp, 'unixepoch') > DATETIME('now', ?);
        """

    args = (pcuid, epid, date)
    cur = db.execute(sql, args)
    rows = cur.fetchall()

    return rows

def get_score_entries(data, name):
    # Uncomment if you want placeholders in top 10 ranks ala Retro
    #if not name.startswith("my"):
    #    while len(data) < 10:
    #        data.append(((999, 'hehe', 'dong', 1)))

    scores="<{}>\n".format(name)
    rank = 1
    last_score = -1
    for item in data:
        score = item[3]
        if score == last_score:
            rank -= 1
        scores+='\t<score>PCUID="{}" Score="{}" Rank="{}" FirstName="{}" LastName="{}"</score>\n'.format(item[0], score, rank, item[1], item[2])
        rank += 1
        last_score = score
    scores+="</{}>\n".format(name)

    return scores

# route should be something like /getranks
@app.route(f'{route}', methods=['POST'])
def rankings():
    #print("PCUID:", request.form['PCUID'])
    #print("EP_ID:", request.form['EP_ID'])

    # Input Validation
    try:
        pcuid = int(request.form['PCUID'])
        epid = int(request.form['EP_ID'])
        num = 10 if 'NUM' not in request.form else int(request.form['NUM'])
    except ValueError as verr:
        return "Request param does not convert to int", 400
    except Exception as ex:
        return "Error converting request param to int", 500

    # EP_ID must be between 1 and 33. also, ep #6 doesn't exist
    if not (1 <= epid <= 33) or (epid == 6):
        return "Invalid EP_ID", 400

    # Get everything we need from the DB...
    myday = fetch_my_ranks(pcuid, epid, '-1 day')
    day = fetch_ranks(epid, '-1 day', num)
    myweek = fetch_my_ranks(pcuid, epid, '-7 day')
    week = fetch_ranks(epid, '-7 day', num)
    mymonth = fetch_my_ranks(pcuid, epid, '-1 month')
    month = fetch_ranks(epid, '-1 month', num)
    myalltime = fetch_my_ranks(pcuid, epid, '-999 year')
    alltime = fetch_ranks(epid, '-999 year', num)

    # Slap that all into an "xml"...
    xmlbody = ""
    xmlbody += get_score_entries(myday, "myday")
    xmlbody += get_score_entries(day, "day")
    xmlbody += get_score_entries(myweek, "myweek")
    xmlbody += get_score_entries(week, "week")
    xmlbody += get_score_entries(mymonth, "mymonth")
    xmlbody += get_score_entries(month, "month")
    xmlbody += get_score_entries(myalltime, "myalltime")
    xmlbody += get_score_entries(alltime, "alltime")

    # and send it off!
    return header + xmlbody

