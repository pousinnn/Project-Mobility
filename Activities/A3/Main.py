# Main.py
import MiModule_1 # estimacion de pose
import MiModule_2 # graficacion
import argparse
import datetime

def main():
	parser = argparse.ArgumentParser("Human traits", description = "This code generates a folder tree to classify human traits");
	subparsers = parser.add_subparsers(dest = "cmd");
	
	subparser = subparsers.add_parser("GenDataset",  description = "Generates the dataset");
	subparser.add_argument("--File", required = True, type = str, help = "CSV file comprising the landmarks");
	subparser.add_argument("--SPath", required = True,type = str, help = "Source images path");
	subparser.add_argument("--TPath", required = True,type = str, help = "Target traits path");
	subparser.add_argument("--Split", default = 0.8, type = float, help = "Train/Validation proportion");
	subparser.add_argument("--save_file", action = "store_true");
	subparser.set_defaults(func = MiModule_1.GenDataset);


	subparser = subparsers.add_parser("Plots",  description = "Generates the dataset");
	subparser.add_argument("--File", required = True, type = str, help = "CSV file comprising the landmarks");
	subparser.add_argument("--Folder", required = True, type = str, help = "CSV file comprising the landmarks");	
	subparser.set_defaults(func = MiModule_2.Plots);

	Options = parser.parse_args();
	
	print(str(Options) + "\n");

	Options.func(Options);


if __name__ == "__main__":
	print("\n" + "\033[0;32m" + "[start] " + str(datetime.datetime.now()) + "\033[0m" + "\n");
	main();
	print("\n" + "\033[0;32m" + "[end] "+ str(datetime.datetime.now()) + "\033[0m" + "\n");