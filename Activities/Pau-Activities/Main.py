import LIB
import argparse
import datetime

def main():
	parser = argparse.ArgumentParser("A3", description = "A3 for TC2008b");
	subparsers = parser.add_subparsers(dest = "cmd", required = True);

	subparser = subparsers.add_parser("Sim",  description = "Shows the last recorded simulation in the browser");
	subparser.add_argument("--Port", default = 5000, type = int, help = "Port of the web viewer");
	subparser.set_defaults(func = LIB.Sim);

	subparser = subparsers.add_parser("Parameters",  description = "Runs the simulation with the given parameters and records it");
	subparser.add_argument("--M", default = 8, type = int, help = "Rows of the room grid");
	subparser.add_argument("--N", default = 8, type = int, help = "Columns of the room grid");
	subparser.add_argument("--Agents", default = 1, type = int, help = "Number of agents");
	subparser.add_argument("--Dirty", default = 0.3, type = float, help = "Fraction of free cells that are dirty (0-1)");
	subparser.add_argument("--Locked", default = 0.1, type = float, help = "Fraction of cells agents can not visit (0-1)");
	subparser.add_argument("--MaxTime", default = 300, type = int, help = "Maximum simulation time (steps)");
	subparser.add_argument("--Trajectory", default = "zigzag", choices = ["zigzag", "random", "local"], help = "Planning method");
	subparser.add_argument("--Start", default = 0, type = int, help = "Start cell of every agent");
	subparser.add_argument("--Seed", default = 1, type = int, help = "Random seed");
	subparser.add_argument("--AgentsList", default = None, type = int, nargs = "+", help = "Analysis: numbers of agents to test (e.g. 1 2 4 8)");
	subparser.add_argument("--Trajectories", default = None, nargs = "+", choices = ["zigzag", "random", "local"], help = "Analysis: planning methods to test");
	subparser.add_argument("--Repeats", default = 20, type = int, help = "Analysis: runs per combination");
	subparser.add_argument("--BaseSeed", default = 1, type = int, help = "Analysis: seed of the first run");
	subparser.set_defaults(func = LIB.Parameters);

	Options = parser.parse_args();

	print(str(Options) + "\n");

	Options.func(Options);


if __name__ == "__main__":
	print("\n" + "\033[0;32m" + "[start] " + str(datetime.datetime.now()) + "\033[0m" + "\n");
	main();
	print("\n" + "\033[0;32m" + "[end] "+ str(datetime.datetime.now()) + "\033[0m" + "\n");