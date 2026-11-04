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
    def __init__(self, size=50):
        super().__init__()
        self.size = size
        self.grid = numpy.zeros((size, size), dtype=numpy.uint8)

        self.cells = [
            [XORCell(self, r, c) for c in range(size)]
            for r in range(size)
        ]

        self.grid[0, size // 2] = 1
        self.cells[0][size // 2].state = 1
        self.step_count = 0

    def step(self):
        r = self.step_count + 1
        if r >= self.size:
            self.running = False
            return

        previous = self.grid[r - 1]
        new_row = numpy.zeros(self.size, dtype=numpy.uint8)

        for c in range(self.size):
            left = previous[c - 1] if c > 0 else 0
            right = previous[c + 1] if c < self.size - 1 else 0
            new_row[c] = left ^ right; # xor operation

        self.grid[r] = new_row

        for c in range(self.size):
            self.cells[r][c].state = int(new_row[c])

        self.step_count += 1

        if self.step_count >= self.size - 1:
            self.running = False

def Automata2GIFF(Options):

    GridSize = Options.GridSize;

    model = XORAutomaton(size = GridSize);
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


