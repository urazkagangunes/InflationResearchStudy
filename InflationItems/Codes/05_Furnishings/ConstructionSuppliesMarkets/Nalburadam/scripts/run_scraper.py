import sys
import os

# Add the scripts directory to the python path so absolute imports like 'import config' work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main

if __name__ == "__main__":
    main()
