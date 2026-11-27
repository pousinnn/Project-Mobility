import csv, ast, flask, pandas, numpy
from pathlib import Path

app = flask.Flask(__name__)
BASE = Path(__file__).resolve().parent

def load_nodes():
    nodes = {}
    with open(BASE / "NodesNew.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            point = tuple(float(v) for v in ast.literal_eval(row["Points"]))
            nodes[int(row["Node"])] = {
                "node": int(row["Node"]),
                "point": point,
                "dirt": int(row["Dirt"])
            }
    return nodes

def load_routes():
    routes = {}
    with open(BASE / "RoutesNew.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            agent = int(row["Agent"])
            routes.setdefault(agent, []).append(int(row["Node"]))
    return routes

@app.route("/")
def index():
    return flask.render_template("index.html")

@app.route("/api/data")
def data():
    return flask.jsonify({"nodes": load_nodes(), "routes": load_routes()})

if __name__ == "__main__":
    app.run(debug=True)

def node_matrix():
    B = numpy.zeros((8,8), dtype = numpy.int32);

    for i in range(8):
        for j in range(8):
            B[i,j] = numpy.ravel_multi_index([i, j], B.shape);

    return B

def zigzag_path():
    B = node_matrix();

    for i in range(8):
        if i % 2 == 0: continue
        B[i,:] = numpy.flip(B[i,:]);

    return B.flatten()

def random_path(steps = 40):
    B = node_matrix();
    moves = numpy.array([[1,0], [-1,0], [0,1], [0,-1]]);

    pos = numpy.array([0, 0]);
    path = [B[pos[0], pos[1]]];

    for _ in range(steps):
        new_pos = pos + moves
        valid = numpy.all((new_pos >= 0) & (new_pos < 8), axis = 1)
        options = new_pos[valid]
        pos = options[numpy.random.randint(len(options))]
        path.append(B[pos[0], pos[1]]);

    return numpy.array(path)

def spiral_path():
    B = node_matrix();
    path = [];

    while B.size > 0:
        path.extend(B[0,:].tolist());
        B = numpy.rot90(B[1:,:]);

    return numpy.array(path)

def region_shape(n):
    # rows x cols of regions, as square as possible (4 -> 2x2, 3 -> 1x3, 6 -> 2x3)
    rows = max(r for r in range(1, int(numpy.sqrt(n)) + 1) if n % r == 0);
    return rows, n // rows

def region_path(k, n):
    B = node_matrix();
    rows, cols = region_shape(n);

    row_blocks = numpy.array_split(numpy.arange(8), rows);
    col_blocks = numpy.array_split(numpy.arange(8), cols);

    R = B[numpy.ix_(row_blocks[k // cols], col_blocks[k % cols])].copy();

    for i in range(R.shape[0]):
        if i % 2 == 0: continue
        R[i,:] = numpy.flip(R[i,:]);

    return R.flatten()

def walk(a, b):
    # cells from node a to node b moving one cell at a time (first rows, then columns)
    ra, ca = numpy.unravel_index(a, (8,8));
    rb, cb = numpy.unravel_index(b, (8,8));
    path = [];

    step = 1 if rb > ra else -1
    for r in range(ra + step, rb + step, step) if ra != rb else []:
        path.append(numpy.ravel_multi_index([r, ca], (8,8)));

    step = 1 if cb > ca else -1
    for c in range(ca + step, cb + step, step) if ca != cb else []:
        path.append(numpy.ravel_multi_index([rb, c], (8,8)));

    return path

def Parameters(Options):
    print(Options.Agents)

    x, y = numpy.meshgrid(numpy.arange(0,8), numpy.arange(0,8));
    Points = numpy.concatenate( [x.flatten().reshape(-1,1), y.flatten().reshape(-1,1)], axis = 1 )
    Points = ["(%d,%d,0)"%(p[0], p[1])  for p in Points.tolist()];

    DF = pandas.DataFrame();

    DF = DF.assign(Node = numpy.arange(0, 64));
    DF = DF.assign(Points = Points);
    DF = DF.assign(Dirt = numpy.where(DF["Node"] == 0, 0, 1));

    print(DF)

    DF.to_csv(BASE / "NodesNew.csv", index = False);

    elevator = 0
    Routes = [];

    for a in range(Options.Agents):
        zone = region_path(a, Options.Agents);
        path = [elevator] + walk(elevator, zone[0]) + zone[1:].tolist() + walk(zone[-1], elevator);
        path = numpy.array(path);
        if zone[0] == elevator:
            path = numpy.concatenate([zone, walk(zone[-1], elevator)]);

        DF = pandas.DataFrame();
        DF = DF.assign( Node = path);
        DF = DF.assign( Agent = a + 1);
        Routes.append(DF);

    DF = pandas.concat(Routes, ignore_index = True);
    DF = DF[["Agent", "Node"]];

    print(DF)

    DF.to_csv(BASE / "RoutesNew.csv", index = False);

def Sim(options):  #python Main.py Sim
    app.run(debug=True)