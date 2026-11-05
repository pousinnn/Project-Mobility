import numpy, mesa
import imageio.v2 as imageio
from matplotlib import pyplot


class XORCell(mesa.Agent):
    def __init__(self, model, row, col):
        super().__init__(model)
        self.row = row
        self.col = col
        self.state = 0

class XORAutomaton(mesa.Model):
    def __init__(self, size=50,sim=1, Density = 0.5):
        super().__init__()
        self.size = size
        self.sim = sim
        self.grid = numpy.zeros((size, size), dtype=numpy.uint8)

        self.cells = [
            [XORCell(self, r, c) for c in range(size)]
            for r in range(size)
        ]
        y = numpy.random.rand(50) > Density
        # self.grid[0, size // 2] = 1
        # self.cells[0][size // 2].state = 1
        if sim == 1:
            self.grid[0] = numpy.random.randint(0, 2, size) # sim 1: random first row
        else:
            self.grid = numpy.random.randint(0, 2, (size, size)).astype(numpy.uint8) # sim 2: random all state
        for r in range(size):
            for c in range(size):
                self.cells[r][c].state = int(self.grid[r, c])
        self.step_count = 0

    def new_kernel(self, x, y, z):
        # TODO
        match f"{x}{y}{z}":
            case "111":
                return 0
            case "110":
                return 1
            case "101":
                return 0
            case "100":
                return 1
            case "011":
                return 1
            case "010":
                return 0
            case "001":
                return 1
            case "000":
                return 0

    def step(self):
        if self.sim == 2:
            self.step2()
            return

        r = self.step_count + 1
        if r >= self.size:
            self.running = False
            return

        previous = self.grid[r - 1]
        new_row = numpy.zeros(self.size, dtype=numpy.uint8)

        for c in range(self.size):
            x = previous[c - 1] if c > 0 else 0
            # y = previous[c + 1] if c < self.size - 1 else 0
            y = previous[c]
            z = previous[c + 1] if c < self.size - 1 else 0
            # new_row[c] = x ^ y; # xor operation
            new_row[c] = self.new_kernel(x, y, z)

        self.grid[r] = new_row

        for c in range(self.size):
            self.cells[r][c].state = int(new_row[c])

        self.step_count += 1

        if self.step_count >= self.size - 1:
            self.running = False

    # sim 2
    def step2(self):
        old = self.grid.copy()

        for r in range(self.size):
            previous = old[r - 1] # row 0 uses the last row as its "up" row
            new_row = numpy.zeros(self.size, dtype=numpy.uint8)

            for c in range(self.size):
                x = previous[c - 1] if c > 0 else 0
                y = previous[c]
                z = previous[c + 1] if c < self.size - 1 else 0
                new_row[c] = self.new_kernel(x, y, z)

            self.grid[r] = new_row

            for c in range(self.size):
                self.cells[r][c].state = int(new_row[c])

        self.step_count += 1

def Automata2GIFF(Options):

    GridSize = Options.GridSize;

    # model = XORAutomaton(size = GridSize);
    model = XORAutomaton(size = GridSize, sim = getattr(Options, "Sim", 1));
    frames = []

    # Initial frame plus one frame for each generated row.
    for _ in range(GridSize):
        fig, ax = pyplot.subplots(figsize=(6, 6))
        ax.imshow(model.grid, cmap="binary", interpolation="nearest", vmin=0, vmax=1)
        ax.set_title(f"XOR Cellular Automaton — Step {model.step_count}")
        ax.set_xlabel("Column")
        ax.set_ylabel("Row")
        ax.set_xticks(numpy.arange(0, GridSize, 5))
        ax.set_yticks(numpy.arange(0, GridSize, 5))
        ax.grid(False)
        fig.tight_layout()

        fig.canvas.draw()
        frame = numpy.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
        frames.append(frame)
        pyplot.close(fig)

        if model.running:
            model.step()

    imageio.mimsave(Options.File, frames, duration =1 / Options.FPS, loop=0)
    print(f"GIF saved as: {Options.File}")
