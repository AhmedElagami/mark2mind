import subprocess
import sys

def download():
    try:
        import spacy
        spacy.load("en_core_web_sm")
    except (OSError, ImportError):
        print("Downloading SpaCy model: en_core_web_sm...")
        subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])

if __name__ == "__main__":
    download()
