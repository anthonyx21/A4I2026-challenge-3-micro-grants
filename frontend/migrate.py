"""Apply the initial versioned application schema and optionally seed the demo."""
import argparse
try:
    from .database import Store
except ImportError:
    from database import Store

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seed',action='store_true')
    args=parser.parse_args()
    database=Store()
    if args.seed: database.seed()
    print('ReliefIQ application schema is ready'+('; demo seed applied without overwriting edits' if args.seed else ''))

if __name__=='__main__': main()
