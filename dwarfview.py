import sys
import pyui
import sdl2
import argparse
import sqlite3
import random
from sdl2.sdlgfx import boxRGBA, polygonColor



def arg_handle():
    parser = argparse.ArgumentParser(description="dwarf legends map")
    parser.add_argument("legends_db", type=str, help='legends sqlite3 database (generate with dwarftime first)')
    return parser


def to_c_int16_arr(ls):
    return (ctypes.c_int16 * len(ls))(*ls)

zoom = 1

class LegendsView(pyui.View):
    def __init__(self, data):
        super().__init__()
        self.data = data

    def draw(self, renderer, rect):
        #boxRGBA(renderer, 10, 10, 20, 20, 0, 0, 0, 255)
        for rid, name, rtype, coords, evilness in data:
            coordlist = coords.split("|")
            print(coordlist)

            vx = to_c_int16_arr([int(x.split(",")[0]) * zoom for x in coordlist])
            vy = to_c_int16_arr([int(x.split(",")[1]) * zoom for x in coordlist])
            n = len(coordlist)
            print(vx)
            print(vy)
            polygonColor(renderer, vx, vy, n, 23423223)




if __name__ == "__main__":
    args = arg_handle().parse_args()
    fn = args.legends_db
    db = sqlite3.connect(fn)
    cur = db.cursor()
    data = []
    it = cur.execute("select id,name,type,coords,evilness from regions")
    for row in it.fetchall():
        print(row)
        data.append(row)

    app = pyui.Application("club.thingstead.DwarfLegendsDatabase")
    app.window("DwarfLegends", LegendsView(data))
    app.run()
