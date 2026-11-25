import LIB
import argparse
import datetime

def main():
	parser = argparse.ArgumentParser("A3", description = "A3 for TC2008b");
	subparsers = parser.add_subparsers();
	
	subparser = subparsers.add_parser("Sim",  description = "Runs the simulation");
	subparser.add_argument("--Split", default = 0.8, type = float, help = "Train/Validation proportion");
	subparser.set_defaults(func = LIB.Sim);

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