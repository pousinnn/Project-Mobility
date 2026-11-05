import csv, ast, flask
from pathlib import Path

app = flask.Flask(__name__)
BASE = Path(__file__).resolve().parent

def load_nodes():
    nodes = {}
    with open(BASE / "Nodes.csv", newline="", encoding="utf-8") as f:
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
    with open(BASE / "Routes.csv", newline="", encoding="utf-8") as f:
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
