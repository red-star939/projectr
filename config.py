import os
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.normpath(os.path.join(current_dir, "../../.env"))

load_dotenv(dotenv_path=env_path)

DART_API_KEY = os.getenv("DART_API_KEY")