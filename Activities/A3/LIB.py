import ast, math
from collections import deque
from pathlib import Path

import flask, numpy, pandas

app = flask.Flask(__name__)
BASE = Path(__file__).resolve().parent

MOVES = ((0, 1), (0, -1), (1, 0), (-1, 0))


# ---------------------------------------------------------------------------
# Grid helpers (node = numpy.ravel_multi_index([row, col], (M, N)))
# ---------------------------------------------------------------------------

def node_matrix(M = 8, N = 8):
    B = numpy.zeros((M, N), dtype = numpy.int32);

    for i in range(M):
        for j in range(N):
            B[i, j] = numpy.ravel_multi_index([i, j], B.shape);

    return B

def zigzag_order(M, N):
    B = node_matrix(M, N);

    for i in range(M):
        if i % 2 == 0: continue
        B[i, :] = numpy.flip(B[i, :]);

    return B.flatten().tolist()

def spiral_order(M, N):
    B = node_matrix(M, N);
    order = [];

    while B.size > 0:
        order.extend(B[0, :].tolist());
        B = numpy.rot90(B[1:, :]);

    return order


class Room:
    def __init__(self, M, N, locked, dirty, chargers):
        self.M, self.N = M, N
        self.locked = set(locked)
        self.dirty = set(dirty)
        self.initial_dirty = set(dirty)
        self.chargers = list(chargers)
        self.free = [c for c in range(M * N) if c not in self.locked]

    def rc(self, cell):
        return divmod(cell, self.N)

    def neighbors(self, cell):
        r, c = self.rc(cell)
        for dr, dc in MOVES:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.M and 0 <= nc < self.N:
                n = nr * self.N + nc
                if n not in self.locked:
                    yield n

    def bfs(self, sources):
        """Distance (in moves) from the closest source to every reachable cell."""
        dist = {s: 0 for s in sources}
        queue = deque(sources)
        while queue:
            cell = queue.popleft()
            for n in self.neighbors(cell):
                if n not in dist:
                    dist[n] = dist[cell] + 1
                    queue.append(n)
        return dist

    def path_to(self, start, is_goal):
        """Shortest path from start to the closest cell that satisfies is_goal."""
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


def make_room(Options, rng):
    M, N = Options.M, Options.N
    cells = numpy.arange(M * N)

    # Charging stations = start cells of the agents
    if Options.Sim == 1:
        chargers = [0]
    else:
        chargers = rng.choice(cells, size = Options.Agents, replace = False).tolist()

    candidates = numpy.setdiff1d(cells, chargers)
    n_locked = int(round(Options.Locked * M * N))
    locked = rng.choice(candidates, size = min(n_locked, len(candidates)), replace = False).tolist()

    free = numpy.setdiff1d(candidates, locked)
    n_dirty = int(round(Options.Dirty * (M * N - len(locked))))
    dirty = rng.choice(free, size = min(n_dirty, len(free)), replace = False).tolist()

    return Room(M, N, locked, dirty, chargers)


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class Agent:
    def __init__(self, agent_id, home, battery):
        self.id = agent_id
        self.pos = home
        self.home = home
        self.max_battery = battery
        self.battery = battery
        self.mode = "work"          # work | return | done
        self.finished = False       # no more work to do
        self.path = []
        self.target = None
        self.moves = 0
        self.recharges = 0
        self.cleaned = 0


class Simulation:
    def __init__(self, Options, rng):
        self.Options = Options
        self.rng = rng
        self.room = make_room(Options, rng)
        room = self.room

        n_agents = 1 if Options.Sim == 1 else Options.Agents
        self.agents = [Agent(i + 1, room.chargers[i], Options.Battery) for i in range(n_agents)]

        # Simulation 1: only its own start point. Simulation 2: any agent's start point.
        self.dist_charger = {a.id: room.bfs([a.home] if Options.Sim == 1 else room.chargers)
                             for a in self.agents}
        self.reachable = set(room.bfs(room.chargers).keys())
        self.reachable_dirty = room.dirty & self.reachable
        self.reserve = max(1, math.ceil(0.05 * Options.Battery))

        orders = {"zigzag": zigzag_order, "spiral": spiral_order}
        self.order = orders.get(Options.Trajectory, zigzag_order)(room.M, room.N)
        self.order = [c for c in self.order if c in self.reachable]

        self.visited = set(a.pos for a in self.agents)
        self.first_visit = {a.pos: 0 for a in self.agents}
        self.cleaned_at = {}
        self.claimed = {}
        self.history = []
        self.progress = []
        self.time_to_clean = None
        self.step_count = 0

    # ----- target selection per trajectory type -----
    def next_path(self, agent):
        room = self.room
        taken = set(t for aid, t in self.claimed.items() if aid != agent.id)
        trajectory = self.Options.Trajectory

        if trajectory == "random":
            options = list(room.neighbors(agent.pos))
            return [options[self.rng.integers(len(options))]] if options else None

        if trajectory == "local":
            # Greedy local search: closest dirty cell that nobody else is going to
            path = room.path_to(agent.pos, lambda c: c in room.dirty and c not in taken)
            if path is None:
                # no dirt left reachable: explore closest unvisited cell
                path = room.path_to(agent.pos, lambda c: c not in self.visited and c not in taken)
            return path

        # zigzag / spiral: first cell of the order that nobody visited or claimed
        for cell in self.order:
            if cell not in self.visited and cell not in taken and cell != agent.pos:
                return room.path_to(agent.pos, lambda c, cell = cell: c == cell)
        return None

    def move(self, agent, cell, t):
        agent.pos = cell
        agent.battery -= 1
        agent.moves += 1
        if cell not in self.visited:
            self.visited.add(cell)
            self.first_visit[cell] = t
        if cell in self.room.dirty:
            self.room.dirty.discard(cell)
            self.cleaned_at[cell] = t
            agent.cleaned += 1

    def step_agent(self, agent, t):
        room = self.room
        dist = self.dist_charger[agent.id]

        if agent.mode == "done":
            return "done"

        # Recharge when it is back at a charging station
        if agent.mode == "return" and dist.get(agent.pos, 1) == 0:
            if agent.finished:
                agent.mode = "done"
                return "done"
            agent.battery = agent.max_battery
            agent.recharges += 1
            agent.mode = "work"
            return "charge"

        if agent.mode == "work":
            if not agent.path:
                agent.path = self.next_path(agent) or []
                agent.target = agent.path[-1] if agent.path else None
                if agent.target is not None:
                    self.claimed[agent.id] = agent.target
                else:
                    agent.finished = True
                    agent.mode = "return"
                    self.claimed.pop(agent.id, None)

            if agent.mode == "work":
                nxt = agent.path[0]
                # Battery check: after this move it must still be able to reach a charger
                # arriving with at least 5% of the battery left.
                if agent.battery - 1 < dist.get(nxt, math.inf) + self.reserve:
                    agent.mode = "return"
                    agent.path = []
                    self.claimed.pop(agent.id, None)
                else:
                    agent.path.pop(0)
                    self.move(agent, nxt, t)
                    if not agent.path:
                        self.claimed.pop(agent.id, None)
                    return "clean" if self.cleaned_at.get(nxt) == t else "move"

        if agent.mode == "return":
            here = dist.get(agent.pos, math.inf)
            if here == 0:
                return self.step_agent(agent, t)
            options = [n for n in room.neighbors(agent.pos) if dist.get(n, math.inf) == here - 1]
            if options:
                self.move(agent, options[0], t)
                return "return"
        return "idle"

    def run(self):
        Options = self.Options
        for a in self.agents:
            self.history.append([0, a.id, a.pos, a.battery, "start"])
        self.record_progress(0)

        for t in range(1, Options.MaxTime + 1):
            for a in self.agents:
                action = self.step_agent(a, t)
                self.history.append([t, a.id, a.pos, a.battery, action])
            self.record_progress(t)
            self.step_count = t

            if not (self.reachable_dirty & self.room.dirty):
                self.time_to_clean = t
                break
            if all(a.mode == "done" for a in self.agents):
                break
        return self

    def record_progress(self, t):
        room = self.room
        self.progress.append([t,
                              len(self.cleaned_at),
                              100 * len(self.cleaned_at) / max(1, len(room.initial_dirty)),
                              100 * len(self.visited) / max(1, len(room.free))])

    # ----- results -----
    def results(self):
        room = self.room
        rows = []
        for a in self.agents:
            rows.append({"Agent": a.id, "Start": a.home, "Moves": a.moves,
                         "Recharges": a.recharges, "CellsCleaned": a.cleaned})
        DF = pandas.DataFrame(rows)

        summary = {
            "Simulation": self.Options.Sim,
            "Grid": f"{room.M}x{room.N}",
            "Agents": len(self.agents),
            "Trajectory": self.Options.Trajectory,
            "DirtyPct": self.Options.Dirty * 100,
            "LockedPct": self.Options.Locked * 100,
            "Battery": self.Options.Battery,
            "MaxTime": self.Options.MaxTime,
            "Seed": self.Options.Seed,
            "FreeCells": len(room.free),
            "DirtyCells": len(room.initial_dirty),
            "LockedCells": len(room.locked),
            "StepsSimulated": self.step_count,
            "TimeToClean": self.time_to_clean if self.time_to_clean is not None else -1,
            "VisitedPct": round(100 * len(self.visited) / max(1, len(room.free)), 2),
            "CleanedPct": round(100 * len(self.cleaned_at) / max(1, len(room.initial_dirty)), 2),
            "TotalMoves": int(DF["Moves"].sum()),
            "MeanMovesPerAgent": round(float(DF["Moves"].mean()), 2),
            "TotalRecharges": int(DF["Recharges"].sum()),
        }
        return summary, DF

    def save(self, prefix = "Sim"):
        room = self.room
        summary, DF = self.results()

        B = node_matrix(room.M, room.N)
        rows, cols = numpy.unravel_index(B.flatten(), B.shape)
        Nodes = pandas.DataFrame();
        Nodes = Nodes.assign(Node = B.flatten());
        Nodes = Nodes.assign(Points = ["(%d,%d,0)" % (c, r) for r, c in zip(rows, cols)]);
        Nodes = Nodes.assign(Dirt = [int(n in room.initial_dirty) for n in Nodes["Node"]]);
        Nodes = Nodes.assign(Locked = [int(n in room.locked) for n in Nodes["Node"]]);
        Nodes = Nodes.assign(Charger = [int(n in room.chargers) for n in Nodes["Node"]]);
        Nodes = Nodes.assign(CleanedAt = [self.cleaned_at.get(n, -1) for n in Nodes["Node"]]);
        Nodes = Nodes.assign(FirstVisit = [self.first_visit.get(n, -1) for n in Nodes["Node"]]);
        Nodes.to_csv(BASE / f"{prefix}Nodes.csv", index = False);

        Routes = pandas.DataFrame(self.history, columns = ["Step", "Agent", "Node", "Battery", "Action"])
        Routes.to_csv(BASE / f"{prefix}Routes.csv", index = False);

        Progress = pandas.DataFrame(self.progress, columns = ["Step", "Cleaned", "CleanedPct", "VisitedPct"])
        Progress.to_csv(BASE / f"{prefix}Progress.csv", index = False);

        DF.to_csv(BASE / f"{prefix}Agents.csv", index = False);
        pandas.DataFrame([summary]).to_csv(BASE / f"{prefix}Results.csv", index = False);
        return summary, DF


def print_results(summary, DF):
    print("\n=== Simulation results ===")
    for k, v in summary.items():
        print(f"{k:>20}: {v}")
    print("\nPer agent:")
    print(DF.to_string(index = False))


def run_simulation(Options):
    rng = numpy.random.default_rng(Options.Seed)
    return Simulation(Options, rng).run()


# ---------------------------------------------------------------------------
# Web viewer
# ---------------------------------------------------------------------------

def load_sim():
    Nodes = pandas.read_csv(BASE / "SimNodes.csv")
    Routes = pandas.read_csv(BASE / "SimRoutes.csv")
    Results = pandas.read_csv(BASE / "SimResults.csv").iloc[0].to_dict()

    nodes = {}
    for _, row in Nodes.iterrows():
        nodes[int(row["Node"])] = {
            "node": int(row["Node"]),
            "point": [float(v) for v in ast.literal_eval(row["Points"])],
            "dirt": int(row["Dirt"]),
            "locked": int(row["Locked"]),
            "charger": int(row["Charger"]),
            "cleanedAt": int(row["CleanedAt"]),
            "firstVisit": int(row["FirstVisit"]),
        }

    routes, battery, actions = {}, {}, {}
    for agent, group in Routes.groupby("Agent"):
        group = group.sort_values("Step")
        routes[int(agent)] = group["Node"].astype(int).tolist()
        battery[int(agent)] = group["Battery"].astype(int).tolist()
        actions[int(agent)] = group["Action"].tolist()

    results = {k: (v.item() if hasattr(v, "item") else v) for k, v in Results.items()}
    return {"nodes": nodes, "routes": routes, "battery": battery, "actions": actions,
            "results": results}

@app.route("/")
def index():
    return flask.render_template("index.html")

@app.route("/api/data")
def data():
    return flask.jsonify(load_sim())


# ---------------------------------------------------------------------------
# Commands called from Main.py
# ---------------------------------------------------------------------------

def Sim(Options):  # python Main.py Sim --Sim 1 ...
    sim = run_simulation(Options)
    summary, DF = sim.save("Sim")
    print_results(summary, DF)
    print("\nSaved: SimNodes.csv, SimRoutes.csv, SimProgress.csv, SimAgents.csv, SimResults.csv")

    if not Options.NoServer:
        print("\nOpen http://127.0.0.1:%d to watch the simulation" % Options.Port)
        app.run(debug = True, use_reloader = False, port = Options.Port)

def Experiments(Options):  # python Main.py Experiments --AgentsList 1 2 4 8
    rows = []
    for n_agents in Options.AgentsList:
        for r in range(Options.Repeats):
            Options.Agents = n_agents
            Options.Seed = Options.BaseSeed + r
            sim = run_simulation(Options)
            summary, _ = sim.results()
            rows.append(summary)
            print(f"Agents={n_agents:>2} repeat={r} time={summary['TimeToClean']:>4} "
                  f"cleaned={summary['CleanedPct']:6.2f}% visited={summary['VisitedPct']:6.2f}% "
                  f"moves/agent={summary['MeanMovesPerAgent']}")

    DF = pandas.DataFrame(rows)
    DF.to_csv(BASE / "Experiments.csv", index = False)

    Summary = DF.groupby("Agents").agg(
        TimeToClean = ("TimeToClean", lambda s: s[s > 0].mean() if (s > 0).any() else float("nan")),
        Finished = ("TimeToClean", lambda s: int((s > 0).sum())),
        CleanedPct = ("CleanedPct", "mean"),
        VisitedPct = ("VisitedPct", "mean"),
        MeanMovesPerAgent = ("MeanMovesPerAgent", "mean"),
        TotalMoves = ("TotalMoves", "mean"),
        TotalRecharges = ("TotalRecharges", "mean"),
    ).round(2).reset_index()
    Summary.to_csv(BASE / "ExperimentsSummary.csv", index = False)
    print("\n=== Average per number of agents ===")
    print(Summary.to_string(index = False))

    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot
    fig, axes = pyplot.subplots(1, 3, figsize = (14, 4))
    axes[0].plot(Summary["Agents"], Summary["TimeToClean"], "o-")
    axes[0].set_title("Time to clean (steps)")
    axes[1].plot(Summary["Agents"], Summary["CleanedPct"], "o-", label = "Cleaned %")
    axes[1].plot(Summary["Agents"], Summary["VisitedPct"], "s--", label = "Visited %")
    axes[1].set_title("Coverage (%)"); axes[1].legend()
    axes[2].plot(Summary["Agents"], Summary["MeanMovesPerAgent"], "o-")
    axes[2].set_title("Movements per agent")
    for ax in axes:
        ax.set_xlabel("Number of agents"); ax.grid(True, alpha = 0.3)
        ax.set_xticks(Summary["Agents"])
    fig.suptitle(f"{Options.M}x{Options.N} grid, {Options.Trajectory}, "
                 f"dirty {Options.Dirty*100:.0f}%, locked {Options.Locked*100:.0f}%, "
                 f"battery {Options.Battery}, {Options.Repeats} repeats")
    fig.tight_layout()
    fig.savefig(BASE / "Experiments.png", dpi = 150)
    print("\nSaved: Experiments.csv, ExperimentsSummary.csv, Experiments.png")


# ---------------------------------------------------------------------------
# Previous exercise (8x8 grid with zigzag / random / spiral routes)
# ---------------------------------------------------------------------------

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
    patterns = [lambda: numpy.array(zigzag_order(8, 8)), random_path,
                lambda: numpy.array(spiral_order(8, 8))]
    Routes = [];

    for a in range(Options.Agents):
        path = patterns[a % len(patterns)]();
        if path[-1] != elevator:
            path = numpy.append(path, elevator);

        DF = pandas.DataFrame();
        DF = DF.assign( Node = path);
        DF = DF.assign( Agent = a + 1);
        Routes.append(DF);

    DF = pandas.concat(Routes, ignore_index = True);
    DF = DF[["Agent", "Node"]];

    print(DF)

    DF.to_csv(BASE / "RoutesNew.csv", index = False);