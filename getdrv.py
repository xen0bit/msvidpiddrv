import argparse
from bs4 import BeautifulSoup
import requests
import re
import json
import urllib.parse
from pprint import pprint
from tqdm import tqdm
import sqlite3


def getDownload(uid):
    body = f"updateIDs=%5B%7B%22size%22%3A0%2C%22languages%22%3A%22%22%2C%22uidInfo%22%3A%22{uid}%22%2C%22updateID%22%3A%22{uid}%22%7D%5D&updateIDsBlockedForImport=&wsusApiPresent=&contentImport=&sku=&serverName=&ssl=&portNumber=&version="
    resp = requests.post(
        "https://www.catalog.update.microsoft.com/DownloadDialog.aspx",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    downloadInformation = r"downloadInformation\[0\]\.files\[0\]\.(.*);"
    di = re.findall(downloadInformation, resp.text)
    fileinfo = {}
    for info in di:
        infoparts = info.split("=", 1)
        key = infoparts[0].strip()
        value = infoparts[1].replace("'", "").strip()
        fileinfo[key] = value

    return fileinfo


def parseSearch(resp):
    results = []
    html = BeautifulSoup(resp, "html.parser")
    ut = html.select_one("#ctl00_catalogBody_updateMatches")
    if ut is not None:
        utrs = ut.find_all("tr")
        for tr in utrs:
            if tr.get("id") != "headerRow":
                tds = tr.find_all("td")
                if len(tds) == 8:
                    results.append(
                        {
                            "title": tds[1].find("a").text.strip(),
                            "products": tds[2].text.strip(),
                            "classification": tds[3].text.strip(),
                            "lastUpdated": tds[4].text.strip(),
                            "version": tds[5].text.strip(),
                            "size": tds[6].select_one("span.noDisplay").text,
                            "updateID": tds[7]
                            .select_one('input[value="Download"]')
                            .get("id"),
                        }
                    )
    return results


def doSearch(vid, pid, page):
    resp = requests.get(
        f"https://www.catalog.update.microsoft.com/Search.aspx?q=vid_{vid}%26pid_{pid}&p={page}"
    )
    return resp.text


def fetchUpdates(dbconn, vid, pid):
    dbcur = dbconn.cursor()
    dbcur.execute(
        """
                    CREATE TABLE IF NOT EXISTS "updates" (
                        "id"	INTEGER,
                        "title"	TEXT,
                        "products"	TEXT,
                        "classification"	TEXT,
                        "lastUpdated"	TEXT,
                        "version"	TEXT,
                        "size"	TEXT,
                        "updateID"	TEXT UNIQUE,
                        "architectures"	TEXT,
                        "defaultFileNameLength"	TEXT,
                        "digest"	TEXT,
                        "fileName"	TEXT,
                        "languages"	TEXT,
                        "longLanguages"	TEXT,
                        "sha256"	TEXT,
                        "url"	TEXT,
                        PRIMARY KEY("id" AUTOINCREMENT)
                    );
"""
    )
    # updates = []
    page = 0
    while True:
        resp = doSearch(vid, pid, page)
        results = parseSearch(resp)
        if len(results) == 0:
            break
        print(f"Scraping page: {page}")
        for result in tqdm(results):
            fileinfo = getDownload(result["updateID"])
            # Replace with a db insert
            # updates.append(result | fileinfo)
            t = result | fileinfo
            dbcur.execute(
                """
                            INSERT OR IGNORE INTO updates (title, products, classification, lastUpdated, version, size, updateID, architectures, defaultFileNameLength, digest, fileName, languages, longLanguages, sha256, url) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
""",
                (
                    t["title"],
                    t["products"],
                    t["classification"],
                    t["lastUpdated"],
                    t["version"],
                    t["size"],
                    t["updateID"],
                    t["architectures"],
                    t["defaultFileNameLength"],
                    t["digest"],
                    t["fileName"],
                    t["languages"],
                    t["longLanguages"],
                    t["sha256"],
                    t["url"],
                ),
            )
        page += 1

    # return updates


def main():
    parser = argparse.ArgumentParser(description="Process vid and pid arguments.")
    # parser.add_argument('vid', type=str, help='Vendor ID', default='1532')
    # parser.add_argument('pid', type=str, help='Product ID', default='0241')
    args = parser.parse_args()

    args.vid = "1532"
    args.pid = "0241"
    args.db = "updates.db"

    with sqlite3.connect(args.db) as con:
        # print(f"VID: {args.vid}")
        # print(f"PID: {args.pid}")

        ct = 0
        with open("vidpid.csv", "r") as f:
            for line in f:
                if ct >= 100:
                    break
                vid, pid = line.strip().split(",")
                print(vid, pid)
                fetchUpdates(con, vid, pid)
                ct += 1


if __name__ == "__main__":
    main()
