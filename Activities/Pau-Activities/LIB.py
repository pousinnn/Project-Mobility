import ast, csv
from collections import deque
from pathlib import Path

import flask, numpy, pandas

app = flask.Flask(__name__)
BASE = Path(__file__).resolve().parent

MOVES = ((1, 0), (-1, 0), (0, 1), (0, -1))


# ---------------------------------------------------------------------------
# Web viewer (python Main.py Sim)
# ---------------------------------------------------------------------------

def load_nodes():
    nodes = {}
    with open(BASE / "NodesNew.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            point = tuple(float(v) for v in ast.literal_eval(row["Points"]))
            nodes[int(row["Node"])] = {
                "node": int(row["Node"]),
                "point": point,
                "dirt": int(row["Dirt"]),
                "locked": int(row["Locked"]),
                "start": int(row["Start"]),
                "cleanedAt": int(row["CleanedAt"]),
                "firstVisit": int(row["FirstVisit"]),
            }
    return nodes

def load_routes():
    routes = {}
    with open(BASE / "RoutesNew.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            agent = int(row["Agent"])
            routes.setdefault(agent, []).append(int(row["Node"]))
    return routes

def load_results():
    Results = pandas.read_csv(BASE / "Results.csv").iloc[0].to_dict()
    return {k: (v.item() if hasattr(v, "item") else v) for k, v in Results.items()}

@app.route("/")
def index():
    return flask.render_template("index.html")

@app.route("/api/data")
def data():
    return flask.jsonify({"nodes": load_nodes(), "routes": load_routes(), "results": load_results()})


# ---------------------------------------------------------------------------
# Room: M x N grid, node = numpy.ravel_multi_index([row, col], (M, N))
# ---------------------------------------------------------------------------

def node_matrix(M, N):
    B = numpy.zeros((M, N), dtype = numpy.int32);

    for i in range(M):
        for j in range(N):
            B[i,j] = numpy.ravel_multi_index([i, j], B.shape);

    return B

def zigzag(B):
    B = B.copy();

    for i in range(B.shape[0]):
        if i % 2 == 0: continue
        B[i,:] = numpy.flip(B[i,:]);

    return B.flatten()

def region_shape(n):
    # rows x cols of regions, as square as possible (4 -> 2x2, 3 -> 1x3, 6 -> 2x3)
    rows = max(r for r in range(1, int(numpy.sqrt(n)) + 1) if n % r == 0);
    return rows, n // rows

def region_zigzag(B, k, n):
    rows, cols = region_shape(n);
    row_blocks = numpy.array_split(numpy.arange(B.shape[0]), rows);
    col_blocks = numpy.array_split(numpy.arange(B.shape[1]), cols);

    R = B[numpy.ix_(row_blocks[k // cols], col_blocks[k % cols])];
    return zigzag(R) if R.size > 0 else numpy.array([], dtype = numpy.int32)


class Room:
    def __init__(self, Options, rng):
        self.M, self.N = Options.M, Options.N
        self.B = node_matrix(self.M, self.N)
        cells = self.B.flatten()
        self.start = Options.Start

        # Locked cells at random (never the start cell)
        candidates = numpy.setdiff1d(cells, [self.start])
        n_locked = int(round(Options.Locked * self.M * self.N))
        self.locked = set(rng.choice(candidates, size = min(n_locked, len(candidates)), replace = False).tolist())

        # Dirty cells at random among the free cells the agents can reach
        self.reachable = set(self.bfs(self.start).keys())
        free = numpy.array(sorted(self.reachable - {self.start}))
        n_dirty = int(round(Options.Dirty * (self.M * self.N - len(self.locked))))
        self.dirty = set(rng.choice(free, size = min(n_dirty, len(free)), replace = False).tolist()) if len(free) else set()
        self.initial_dirty = set(self.dirty)
        self.free = [c for c in cells.tolist() if c not in self.locked]

    def neighbors(self, cell):
        r, c = numpy.unravel_index(cell, (self.M, self.N))
        for dr, dc in MOVES:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.M and 0 <= nc < self.N:
                n = int(numpy.ravel_multi_index([nr, nc], (self.M, self.N)))
                if n not in self.locked:
                    yield n

    def bfs(self, source):
        dist = {source: 0}
        queue = deque([source])
        while queue:
            cell = queue.popleft()
            for n in self.neighbors(cell):
                if n not in dist:
                    dist[n] = dist[cell] + 1
                    queue.append(n)
        return dist

    def path_to(self, start, is_goal):
        """Shortest path (avoiding locked cells) to the closest cell where is_goal is true."""
        parent = {start: None}
        queue = deque([start])
        while queue:
            cell = queue.popleft()
            if cell != start and is_goal(cell):
                path = []
                while cell != start:
                    path.append(cell)
                    cell = parent[cell]
                return path[::-1]
            for n in self.neighbors(cell):
                if n not in parent:
                    parent[n] = cell
                    queue.append(n)
        return None


# ---------------------------------------------------------------------------
# Agents and the three planning methods
# ---------------------------------------------------------------------------

class Agent:
    def __init__(self, agent_id, start):
        self.id = agent_id
        self.pos = start
        self.path = []
        self.order = []         # zigzag: cells of its region, in zigzag order
        self.done = False
        self.moves = 0
        self.cleaned = 0


class Simulation:
    def __init__(self, Options, rng):
        self.Options = Options
        self.rng = rng
        self.room = Room(Options, rng)
        room = self.room

        self.agents = [Agent(i + 1, room.start) for i in range(Options.Agents)]

        # Zigzag: each agent sweeps its own region of the room
        for k, a in enumerate(self.agents):
            a.order = [c for c in region_zigzag(room.B, k, Options.Agents).tolist() if c in room.reachable]

        self.visited = {room.start}
        self.first_visit = {room.start: 0}
        self.cleaned_at = {}
        self.claimed = {}
        self.history = [[0, a.id, a.pos] for a in self.agents]
        self.time_to_clean = None
        self.steps = 0

    def plan(self, agent):
        room = self.room
        method = self.Options.Trajectory

        if method == "random":
            # Random walk: any free neighbour
            options = list(room.neighbors(agent.pos))
            return [options[self.rng.integers(len(options))]] if options else []

        if method == "local":
            # Local search: closest dirty cell (shortest path) that no other agent claimed
            taken = set(t for aid, t in self.claimed.items() if aid != agent.id)
            return room.path_to(agent.pos, lambda c: c in room.dirty and c not in taken) or []

        # Zigzag: next unvisited cell of its own region
        while agent.order and agent.order[0] in self.visited:
            agent.order.pop(0)
        if not agent.order:
            return []
        if agent.order[0] == agent.pos:
            agent.order.pop(0)
            return self.plan(agent)
        target = agent.order[0]
        return room.path_to(agent.pos, lambda c: c == target) or []

    def step_agent(self, agent, t):
        if agent.done:
            return
        if not agent.path:
            agent.path = self.plan(agent)
            if agent.path:
                self.claimed[agent.id] = agent.path[-1]
            else:
                agent.done = True
                self.claimed.pop(agent.id, None)
                return

        cell = agent.path.pop(0)
        agent.pos = cell
        agent.moves += 1
        if cell not in self.visited:
            self.visited.add(cell)
            self.first_visit[cell] = t
        if cell in self.room.dirty:
            self.room.dirty.discard(cell)
            self.cleaned_at[cell] = t
            agent.cleaned += 1
        if not agent.path:
            self.claimed.pop(agent.id, None)

    def run(self):
        for t in range(1, self.Options.MaxTime + 1):
            for a in self.agents:
                self.step_agent(a, t)
                self.history.append([t, a.id, a.pos])
            self.steps = t

            if not self.room.dirty:
                self.time_to_clean = t
                break
            if all(a.done for a in self.agents):
                break
        return self

    # ----- recorded data -----
    def results(self):
        room, O = self.room, self.Options
        Agents = pandas.DataFrame([{"Agent": a.id, "Movements": a.moves, "CellsCleaned": a.cleaned}
                                   for a in self.agents])
        summary = {
            "M": O.M, "N": O.N, "Agents": O.Agents, "Trajectory": O.Trajectory,
            "DirtyPct": O.Dirty * 100, "LockedPct": O.Locked * 100, "MaxTime": O.MaxTime,
            "Start": O.Start, "Seed": O.Seed,
            "FreeCells": len(room.free), "DirtyCells": len(room.initial_dirty), "LockedCells": len(room.locked),
            "Steps": self.steps,
            "TimeToClean": self.time_to_clean if self.time_to_clean is not None else -1,
            "AllCleaned": int(not room.dirty),
            "VisitedPct": round(100 * len(self.visited) / max(1, len(room.free)), 2),
            "CleanedPct": round(100 * len(self.cleaned_at) / max(1, len(room.initial_dirty)), 2),
            "TotalMovements": int(Agents["Movements"].sum()),
            "MovementsPerAgent": round(float(Agents["Movements"].mean()), 2),
        }
        return summary, Agents

    def save(self):
        room = self.room
        summary, Agents = self.results()

        rows, cols = numpy.unravel_index(room.B.flatten(), room.B.shape)
        DF = pandas.DataFrame();
        DF = DF.assign(Node = room.B.flatten());
        DF = DF.assign(Points = ["(%d,%d,0)" % (c, r) for r, c in zip(rows, cols)]);
        DF = DF.assign(Dirt = [int(n in room.initial_dirty) for n in DF["Node"]]);
        DF = DF.assign(Locked = [int(n in room.locked) for n in DF["Node"]]);
        DF = DF.assign(Start = [int(n == room.start) for n in DF["Node"]]);
        DF = DF.assign(CleanedAt = [self.cleaned_at.get(n, -1) for n in DF["Node"]]);
        DF = DF.assign(FirstVisit = [self.first_visit.get(n, -1) for n in DF["Node"]]);
        DF.to_csv(BASE / "NodesNew.csv", index = False);

        DF = pandas.DataFrame(self.history, columns = ["Step", "Agent", "Node"]);
        DF = DF[["Agent", "Node", "Step"]].sort_values(["Agent", "Step"]);
        DF.to_csv(BASE / "RoutesNew.csv", index = False);

        Agents.to_csv(BASE / "AgentsResults.csv", index = False);
        pandas.DataFrame([summary]).to_csv(BASE / "Results.csv", index = False);
        return summary, Agents


def run_simulation(Options):
    rng = numpy.random.default_rng(Options.Seed)
    return Simulation(Options, rng).run()


# ---------------------------------------------------------------------------
# Sub-commands called from Main.py
# ---------------------------------------------------------------------------

def Parameters(Options):  # python Main.py Parameters --M 10 --N 10 --Agents 4 ...
    if Options.AgentsList:
        return Analysis(Options)

    sim = run_simulation(Options)
    summary, Agents = sim.save()

    print("=== Simulation results ===")
    for k, v in summary.items():
        print(f"{k:>18}: {v}")
    print("\nPer agent:")
    print(Agents.to_string(index = False))
    print("\nSaved: NodesNew.csv, RoutesNew.csv, Results.csv, AgentsResults.csv")
    print("Run  python Main.py Sim  to watch it")

def Analysis(Options):
    # Design matrix: every combination of agents x trajectory x repetition
    rows = []
    trajectories = Options.Trajectories or [Options.Trajectory]
    for trajectory in trajectories:
        for n_agents in Options.AgentsList:
            for r in range(Options.Repeats):
                Options.Agents, Options.Trajectory, Options.Seed = n_agents, trajectory, Options.BaseSeed + r
                summary, _ = run_simulation(Options).results()
                rows.append(summary)

    Design = pandas.DataFrame(rows)
    Design.insert(0, "Run", numpy.arange(1, len(Design) + 1))
    Design.to_csv(BASE / "DesignMatrix.csv", index = False)

    Summary = Design.groupby(["Trajectory", "Agents"]).agg(
        Runs = ("Run", "count"),
        ProbAllCleaned = ("AllCleaned", "mean"),
        TimeToClean = ("TimeToClean", lambda s: s[s > 0].mean() if (s > 0).any() else float("nan")),
        Steps = ("Steps", "mean"),
        CleanedPct = ("CleanedPct", "mean"),
        VisitedPct = ("VisitedPct", "mean"),
        TotalMovements = ("TotalMovements", "mean"),
        MovementsPerAgent = ("MovementsPerAgent", "mean"),
    ).round(3).reset_index()
    Summary.to_csv(BASE / "AnalysisSummary.csv", index = False)
    print(Summary.to_string(index = False))

    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot
    fig, axes = pyplot.subplots(1, 4, figsize = (18, 4))
    for trajectory, group in Summary.groupby("Trajectory"):
        axes[0].plot(group["Agents"], group["Steps"], "o-", label = trajectory)
        axes[1].plot(group["Agents"], group["MovementsPerAgent"], "o-", label = trajectory)
        axes[2].plot(group["Agents"], group["CleanedPct"], "o-", label = trajectory)
        axes[3].plot(group["Agents"], group["ProbAllCleaned"], "o-", label = trajectory)
    titles = ["Required time (steps)", "Movements per agent", "Task completed (% cleaned)", "P(all dirt cleaned)"]
    for ax, title in zip(axes, titles):
        ax.set_title(title); ax.set_xlabel("Number of agents"); ax.grid(True, alpha = 0.3)
        ax.set_xticks(Options.AgentsList); ax.legend()
    fig.suptitle(f"{Options.M}x{Options.N} room, dirty {Options.Dirty*100:.0f}%, locked {Options.Locked*100:.0f}%, "
                 f"max time {Options.MaxTime}, {Options.Repeats} runs per point")
    fig.tight_layout()
    fig.savefig(BASE / "Analysis.png", dpi = 150)
    print("\nSaved: DesignMatrix.csv, AnalysisSummary.csv, Analysis.png")

def Sim(Options):  # python Main.py Sim
    app.run(debug = True, use_reloader = False, port = Options.Port)