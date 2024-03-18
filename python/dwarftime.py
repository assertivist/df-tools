import sys
import argparse
import sqlite3
import json
from lxml import etree
import os

ROOT_EL = "df_world"

def arg_handler():
    parser = argparse.ArgumentParser(description="dwarf legends")
    parser.add_argument('legends_file', type=str, help='legends xml file')
    return parser

print('The Dwarf Legends Database Generator')


def splitNameSpace(tag):
    if tag[0] == "{":
        return tag[1:].split("}")
    else:
        return None, tag

def parseAttributes(attribs):
    ns = set()
    for attrib in attribs.keys():
        if ':' in attrib:
            ns.add(attrib.split(':')[0])
    if len(ns) == 0:
        return attribs
    else:
        result = {}
        for x in ns:
            result[x] = {}
        for attrib, value in attribs.items():
            if ':' in attrib:
                thisns, tag = attrib.split(':')
                result[thisns]['@'+tag] = value
            else:
                result[attrib] = value
        return result

def parseChildren(tags):
    final = {}

    for x in tags:
        prepend = {}
        result = ''
        uri, tag = splitNameSpace(x.tag)

        if uri is not None:
            prepend['$$'] = uri

        if len(x.attrib) > 0:
            prepend = dict(prepend.items() + parseAttributes(x.attrib).items())
        if len(x) == 0:
            if x.text is not None:
                if len(prepend) == 0:
                    result = x.text
                else:
                    result = dict(prepend.items())
            else:
                if len(prepend) > 0:
                    result = prepend

        else:
            if len(prepend) == 0:
                result = parseChildren(x.getchildren())
            else:
                result = dict(prepend.items() + parseChildren(x.getchildren()))

        if tag in final:
            if type(final[tag]) is not list:
                final[tag] = [final[tag]]

            final[tag].append(result)
        else:
            final[tag] = result

    return final


def df_file_to_dict(fobj, existing=None):
    flines = fobj.readlines()
    tree = etree.fromstring("\n".join(flines[1:]).encode())
    print(tree.tag)
    d = {}
    if existing:
        d = existing
    for collection in tree:
        table_name = collection.tag
        print(table_name)
        columns = []
        rows = []
        for colitem in collection:
            attrs = {}
            if len(colitem) < 1:
                print(f"No children: {colitem.tag}")
                continue
            for attr in colitem:
                attr_name = attr.tag
                if len(attr) > 0:
                    attrs[attr_name] = json.dumps(parseChildren(attr))
                    #exit()
                else:
                    attrs[attr_name] = attr.text
                if attr_name not in columns:
                    columns.append(attr_name)
            rows.append(attrs)
        if table_name in d:
            for c in columns:
                if c not in d[table_name]["cols"]:
                    d[table_name]["cols"].append(c)
            if "id" in columns:
                for row in rows:
                    idx = next((i for i, x in enumerate(d[table_name]["rows"]) if x["id"] == row["id"]), -999)
                    if (idx > -999):
                        d[table_name]["rows"][idx].update(row)
                    else:
                        d[table_name]["rows"].append(row)
        else:
            d[table_name] = {
                "cols": columns,
                "rows": rows
            }
    return d



if __name__ == "__main__":
    args = arg_handler().parse_args()
    fn = args.legends_file
    fn_plus = fn.replace(".xml", "_plus.xml")

    if not os.path.isfile(fn):
        print(f"{fn} was not found.")
        exit(1)
    if not os.path.isfile(fn_plus):
        print(f"{fn_plus} was not found.")
        exit(1)
    sql = "";
    db = sqlite3.connect(fn.replace("xml", "db"))
    cur = db.cursor()
    print(args.legends_file)
    d = {}
    with open(fn, "r", encoding="CP437") as lfile:
        d = df_file_to_dict(lfile)
    with open(fn_plus, "r", encoding="utf-8") as lpfile:
        d = df_file_to_dict(lpfile, existing=d)

    for table_name,table in d.items():
        columnstr = ""
        for col in table["cols"]:
            col = col.replace("group","grp")
            if col == "id":
                columnstr += "id INTEGER PRIMARY KEY"
            elif col.endswith("id"):
                columnstr += f"{col} INTEGER"
            else:
                columnstr += f"{col} TEXT"
            columnstr += ","
        columnstr = columnstr[:-1]
        if len(columnstr) < 1:
            continue

        sql = f"DROP TABLE IF EXISTS {table_name}"
        print(sql)
        cur.execute(sql)
        sql = f"CREATE TABLE {table_name}({columnstr})"
        print(sql)
        cur.execute(sql)
        for row in table["rows"]:
            rcols = list([x.replace('group', 'grp') for x in row.keys()])
            rvals = [row[x] if row[x] else "" for x in row.keys()]
            colstr = ",".join(rcols)
            valstr = ",".join(rvals)
            holes = ("?,"*len(rcols))[:-1]
            confcol = rcols[0]
            rsql = f"INSERT INTO {table_name}({colstr}) VALUES ({holes})"
            if "id" in rcols:
                updatecols = ",".join([f"{x}=excluded.{x}" for x in rcols if x != "id"])
                rsql += f" ON CONFLICT(id) DO UPDATE SET {updatecols}"
            try:
                cur.execute(rsql, rvals)
                #db.commit()
            except (sqlite3.OperationalError,sqlite3.IntegrityError) as error:
                print(error)
                print(colstr,valstr,rsql)
                exit()
    db.commit()
    db.close()
