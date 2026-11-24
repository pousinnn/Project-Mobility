import LIB
import argparse
import datetime

def add_room_arguments(subparser):
	subparser.add_argument("--M", default = 10, type = int, help = "Rows of the room grid");
	subparser.add_argument("--N", default = 10, type = int, help = "Columns of the room grid");
	subparser.add_argument("--Agents", default = 1, type = int, help = "Number of agents (Sim 2)");
	subparser.add_argument("--Dirty", default = 0.3, type = float, help = "Fraction of free cells that are dirty (0-1)");
	subparser.add_argument("--Locked", default = 0.1, type = float, help = "Fraction of cells agents can not visit (0-1)");
	subparser.add_argument("--MaxTime", default = 500, type = int, help = "Maximum simulation time (steps)");
	subparser.add_argument("--Battery", default = 60, type = int, help = "Maximum cells an agent can move before recharging");
	subparser.add_argument("--Trajectory", default = "zigzag", choices = ["zigzag", "spiral", "random", "local"], help = "Trajectory type");
	subparser.add_argument("--Sim", default = 1, type = int, choices = [1, 2], help = "1: one agent at the corner, 2: agents at random start points");

def main():
	parser = argparse.ArgumentParser("A3", description = "A3 for TC2008b");
	subparsers = parser.add_subparsers();

	subparser = subparsers.add_parser("Sim",  description = "Runs the simulation");
	add_room_arguments(subparser);
	subparser.add_argument("--Seed", default = 1, type = int, help = "Random seed");
	subparser.add_argument("--Port", default = 5000, type = int, help = "Port of the web viewer");
	subparser.add_argument("--NoServer", action = "store_true", help = "Only run and save the results");
	subparser.set_defaults(func = LIB.Sim);

	subparser = subparsers.add_parser("Experiments",  description = "Effect of adding more agents");
	add_room_arguments(subparser);
	subparser.add_argument("--AgentsList", default = [1, 2, 4, 8], type = int, nargs = "+", help = "Numbers of agents to test");
	subparser.add_argument("--Repeats", default = 5, type = int, help = "Runs per number of agents");
	subparser.add_argument("--BaseSeed", default = 1, type = int, help = "Seed of the first run");
	subparser.set_defaults(func = LIB.Experiments, Sim = 2);

	subparser = subparsers.add_parser("Parameters",  description = "Runs the paramenters");
	subparser.add_argument("--Agents", default = 1, type = int, help = "Number of agents");
	subparser.set_defaults(func = LIB.Parameters);

	Options = parser.parse_args();

	print(str(Options) + "\n");

	Options.func(Options);


if __name__ == "__main__":
	print("\n" + "\033[0;32m" + "[start] " + str(datetime.datetime.now()) + "\033[0m" + "\n");
	main();
	print("\n" + "\033[0;32m" + "[end] "+ str(datetime.datetime.now()) + "\033[0m" + "\n");