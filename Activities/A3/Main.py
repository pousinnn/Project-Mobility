# Main.py
import LIB # estimacion de pose
import argparse
import datetime

def main():
	parser = argparse.ArgumentParser("A3", description = "A3 for TC2008b");
	subparsers = parser.add_subparsers(dest = "cmd");
	
	subparser = subparsers.add_parser("Sim",  description = "This command runs the simulation");
	subparser.add_argument("--Split", default = 0.8, type = float, help = "Train/Validation proportion");
	subparser.set_defaults(func = LIB.Sim);


	subparser = subparsers.add_parser("Parameters",  description = "Generates the dataset");
	subparser.add_argument("--File", required = True, type = str, help = "CSV file comprising the landmarks");
	subparser.add_argument("--Folder", required = True, type = str, help = "CSV file comprising the landmarks");	
	subparser.set_defaults(func = LIB.Parameters);

	Options = parser.parse_args();
	
	print(str(Options) + "\n");

	Options.func(Options);


if __name__ == "__main__":
	print("\n" + "\033[0;32m" + "[start] " + str(datetime.datetime.now()) + "\033[0m" + "\n");
	main();
	print("\n" + "\033[0;32m" + "[end] "+ str(datetime.datetime.now()) + "\033[0m" + "\n");