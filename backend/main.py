from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Six Degrees API running"}
