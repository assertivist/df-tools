import sys
import pyui
import sdl2
import argparse
import sqlite3
import random
import json
from sdl2.sdlgfx import boxRGBA, filledTrigonRGBA, thickLineRGBA, circleRGBA



def arg_handle():
    parser = argparse.ArgumentParser(description="dwarf legends map")
    parser.add_argument("legends_db", type=str, help='legends sqlite3 database (generate with dwarftime first)')
    return parser


def to_c_int16_arr(ls):
    return (ctypes.c_int16 * len(ls))(*ls)

colors = {
    "Desert": [250, 206, 57, 255],
    "Forest": [41, 141, 17, 255],
    "Hills": [136, 207, 69, 255],
    "Lake": [40, 173, 207, 255],
    "Ocean": [37, 67, 147, 255],
    "Wetland": [96, 160, 132, 255],
    "Mountains": [189, 185, 185, 255],
    "Tundra": [210, 232, 237, 255],
    "Grassland": [186, 237, 78, 255],
    "Glacier": [240, 255, 255, 255]
}

class RegionMap(pyui.View):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self._surface = None
        self.resize((500, 500))
        self.offset_x = 0
        self.offset_y = 0

        self.rects = []
        self.peak_tris = []
        self.rivers = []
        self.sites = []

        for rid, name, rtype, coords, evilness in data['regions']:
            coordlist = coords.split("|")
            for coord in coordlist:
                if len(coord) < 1:
                    continue
                x = int(coord.split(",")[0])
                y = int(coord.split(",")[1])
                c = colors[rtype] if rtype in colors else [0, 0, 0, 255]
                self.rects.append((x, y, c))

        for rid, name, coords, height, is_volcano in data['peaks']:
            loc = [int(i) for i in coords.split(",")]
            c = [45, 45, 45, 255]
            if is_volcano > 0:
                c = [188, 45, 45, 255]
            self.peak_tris.append((*loc, *c))

        for rname, rpath, end_pos in data['rivers']:
            pts = [[int(y) for y in x.split(",")] for x in rpath.split("|") if x]
            pts.append([int(z) for z in end_pos.split(",")])
            self.rivers.append(pts)

        for sid, stype, name, coords, rectangle, structures, site_properties, civ_id, cur_owner_id in data['sites']:
            s = {
                "id": int(sid),
                "coords": [int(x) for x in coords.split(",")],
                "rect": [[int(x) for x in y.split(",")] for y in rectangle.split(":")],
                "structures": json.loads(structures) if structures else {},
                "civ": civ_id,
                "owner": cur_owner_id
            }
            self.sites.append(s)

    def zoom(self, val):
        self.zoom = val
        return self

    def scroll(self, x, y):
        self.offset_x = x
        self.offset_y = y
        return self

    def constrain(self, available=None):
        if available is None:
            available = (500, 500)
        return (500, 500)

    def draw(self, renderer, rect):
        z = self.zoom.value
        ox = self.offset_x.value
        oy = self.offset_y.value
        for x,y,c in self.rects:
            sx = z * x - ox 
            sy = z * y - oy
            ex = (sx + z)
            ey = (sy + z)
            if ex < 0 and ey < 0: continue
            
            boxRGBA(renderer, sx, sy, ex, ey, *c)

        for x, y, r, g, b, a in self.peak_tris:
            msize = int(.3 * z)
            tx = (x * z + int(z / 2.0)) - ox
            ty = (y * z + int(z / 2.0)) - oy
            if tx + msize < 0 and ty + msize < 0:
                continue
            filledTrigonRGBA(
                renderer,
                tx,
                ty - msize,
                tx - msize,
                ty + msize,
                tx + msize,
                ty + msize,
                r, g, b, a) 
        localsize = 12288.0

        """
        for r in self.rivers:
            line = []
            c = colors["Ocean"]
            for pt in r[:-1]:
                wx = pt[0] * z + (z / 2)
                wy = pt[1] * z + (z / 2)
                flow = pt[2]
                exit_tile = pt[3]
                elevation = pt[4]

                line.append((wx, wy))
            
            for p1, p2 in zip(line, line[1:]):
                thickLineRGBA(
                    renderer,
                    p1[0], p1[1],
                    p2[0], p2[1],
                    int(.15 * z), *colors["Ocean"]
                )
        """
        featsize = 2304.0
        for site in self.sites:
            sitecolor = [255, 0, 255, 255]
            x,y = [i * z for i in site["coords"]]
            x1,y1 = [j for j in site["rect"][0]]
            x2,y2 = [k for k in site["rect"][1]]

            x1,x2 = [(int((tx / featsize) * z + x) - ox) for tx in [x1, x2]]
            y1,y2 = [(int((ty / featsize) * z + y) - oy) for ty in [y1, y2]]

            boxRGBA(renderer, x1, y1, x2, y2, *sitecolor)
            circleRGBA(renderer,
                       int((x1 + x2) / 2.0),
                       int((y1 + y2) / 2.0),
                       int(.3 * z),
                       *sitecolor)



min_zoom = 20
max_zoom = 250

class LegendsMapView(pyui.View):
    zoom = pyui.State(int, default=min_zoom)
    offset_x = pyui.State(int, default = 0)
    offset_y = pyui.State(int, default = 0)


    def __init__(self, data):
        super().__init__()
        self.data = data
        self.moving = False
        self.movestart = (0, 0)
        

    def zoom_in(self):
        self.zoom += 5

    def zoom_out(self):
        self.zoom -= 5

    async def mousewheel(self, amt):
        self.zoom.value += amt[1]
        self.zoom.value = max(min_zoom, min(self.zoom.value, max_zoom))
        self.needs_render = True

    async def mousedown(self, pt):
        self.moving = True
        self.movestart = (pt[0] + self.offset_x.value, pt[1] + self.offset_y.value)

    async def mouseup(self, pt):
        self.moving = False

    async def mousemotion(self, pt):
        if self.moving:
            self.offset_x.value = self.movestart[0] - pt[0]
            self.offset_y.value = self.movestart[1] - pt[1]


    def content(self):
        yield pyui.VStack(
            RegionMap(self.data).zoom(self.zoom).scroll(self.offset_x, self.offset_y),
            pyui.Spacer(),
            pyui.Rectangle(
                pyui.VStack(
                    pyui.HStack(
                        pyui.Text("Zoom: "),
                        pyui.Slider(self.zoom, min_zoom, max_zoom),
                        pyui.Text(f"{int(self.zoom.value)}")
                    ),
                    pyui.Text("Hello and welcome to dwarf")
                ).padding(10)
            ).background(55, 55, 55).size(height=25)
        )



if __name__ == "__main__":
    args = arg_handle().parse_args()
    fn = args.legends_db
    db = sqlite3.connect(fn)
    cur = db.cursor()
    data = {}
    data["regions"] = []
    it = cur.execute("select id,name,type,coords,evilness from regions")
    for row in it.fetchall():
        #print(row)
        data["regions"].append(row)

    data["peaks"] = []
    it = cur.execute("select id,name,coords,height,is_volcano is not null as is_volcano from mountain_peaks")
    for row in it.fetchall():
        data["peaks"].append(row)

    data["rivers"] = []
    it = cur.execute("select name,path,end_pos from rivers")
    for row in it.fetchall():
        data["rivers"].append(row)

    data["sites"] = []
    it = cur.execute("select id,type,name,coords,rectangle,structures,site_properties,civ_id,cur_owner_id from sites order by id")
    for row in it.fetchall():
        data["sites"].append(row)

    app = pyui.Application("club.thingstead.DwarfLegendsDatabase")
    app.window("Legends Map", LegendsMapView(data))
    app.run()
