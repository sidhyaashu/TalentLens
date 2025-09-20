import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

folders = [
    "backend/app/api/endpoints",
    "backend/app/core",
    "backend/app/services",
    "backend/app/schemas",
    "frontend"
]

files = [
    "backend/app/api/endpoints/analysis.py",
    "backend/app/core/config.py",
    "backend/app/services/document_parser.py",
    "backend/app/services/scoring_engine.py",
    "backend/app/services/vector_store.py",
    "backend/app/schemas/models.py",
    "backend/app/main.py",
    "backend/Dockerfile",
    "backend/requirements.txt",
    "frontend/dashboard.py",
    "frontend/credentials.json",
    "frontend/Dockerfile",
    "frontend/requirements.txt",
    "docker-compose.yml",
    ".env"
]

def create_folders():
    for folder in folders:
        path = os.path.join(BASE_DIR, folder)
        os.makedirs(path, exist_ok=True)
        print(f"Created folder: {path}")

def create_files():
    for file in files:
        path = os.path.join(BASE_DIR, file)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write("")
            print(f"Created file: {path}")
        else:
            print(f"File already exists: {path}")

if __name__ == "__main__":
    create_folders()
    create_files()
    print("\n✅ Folder structure and files created successfully!")
