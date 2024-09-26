python -m venv .venv
which python
python -m pip install --upgrade pip
echo "*" > .venv/.gitignore
pip install "fastapi[standard]"

source .venv/Scripts/activate
uvicorn main:app --reload