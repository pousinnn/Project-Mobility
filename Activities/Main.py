import LIB_Automata
import argparse
import datetime

def main():
	parser = argparse.ArgumentParser("TC2008B", description = "TC2008B parse");
	subparsers = parser.add_subparsers(dest = "cmd");
	
	subparser = subparsers.add_parser("Automata",  description = "XOR Automata");
	subparser.add_argument("--File", required = False, default = "out.gif", type = str, help = "Output file");
	subparser.add_argument("--GridSize", required = False, default = 50, type = int, help = "Grid Size");
	subparser.add_argument("--FPS", required = False, default = 5, type = int, help = "Frames Per Second");	
	subparser.add_argument("--Density", required = False, default = 0.5, type = float, help = "Density Uniform Distribution");	

	subparser.set_defaults(func = LIB_Automata.Automata2GIFF);

	Options = parser.parse_args();
	
	print(str(Options) + "\n");

	Options.func(Options);


if __name__ == "__main__":
	print("\n" + "\033[0;32m" + "[start] " + str(datetime.datetime.now()) + "\033[0m" + "\n");
	main();
	print("\n" + "\033[0;32m" + "[end] "+ str(datetime.datetime.now()) + "\033[0m" + "\n");
