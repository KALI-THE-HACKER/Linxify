from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import RedirectResponse
import mysql.connector as connector
from mysql.connector.errors import IntegrityError, DatabaseError
import logging
import time
import os

app = FastAPI()

for i in range(10):
    try:
        cnx = connector.connect(
            host="db",
            port='3306',
            user='root',
            password='toor',
            database='linxify'
        )
        break
    except DatabaseError as e:
        print(f"DB connection failed, retrying in 3s... ({i+1}/10)")
        time.sleep(3)
else:
    raise Exception("Failed to connect to DB after multiple attempts")

db_cursor = cnx.cursor()

logging.basicConfig(
    filename='linxifylogs.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

@app.get("/health")
def health():
    return {"health" : "OK!"}

@app.post("/save-url")
async def saveUrl(request: Request, x_api_key: str = Header(...)):
    reserved_urls = {'admin', 'health', 'save-url'}

    x_forwarded_for = request.headers.get('x-forwarded-for')
    ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.client.host
    API_KEY = os.getenv("LINXIFY_API_KEY")

    logging.info(f"Request from IP : {ip}")

    if x_api_key != API_KEY:
        logging.error(f"Invalid API Key, user IP: {ip}")
        raise HTTPException(status_code=401, detail="Invalid API key!")

    try:
        data = await request.json()
        if not data:
            raise HTTPException(status_code=422, detail="Incomplete data provided!")
        
        shortend, long_url = data.get("shortend"), data.get("long_url")

        if shortend in reserved_urls:
            raise HTTPException(
                status_code=400,
                detail={"Error": f"The short URL '{shortend}' is not allowed."}
            )
        
        if not (long_url.startswith("https://") or long_url.startswith("http://")) :
            long_url = "https://" + long_url

        try:
            db_cursor.execute(f"INSERT INTO urls (shortend, long_url, user_ip) VALUES(%s, %s, %s)", (shortend, long_url, ip))

            cnx.commit()
        except IntegrityError as e:
            if e.errno == 1062:
                logging.error(f"Error(Duplicate Primary Key): {e}")
                raise HTTPException(
                    status_code=409,
                    detail={"Error": "Shortened url already exists!"}
                )
            else:
                raise e
                return {"Error ":e}
    except Exception as e:
        logging.error(f'Some error in saving shortend url; Error: {e}')
        raise HTTPException(status_code=500, detail=str(e))

        

    return "DONE"


@app.get("/{short_url}")
def item(short_url):
    db_cursor.execute("SELECT long_url FROM urls WHERE shortend = %s", (short_url,))
    row = db_cursor.fetchone()

    if row:
        return RedirectResponse(url=row[0])
    return {"error": "No URL found!"}

@app.on_event("shutdown")
def shutdown():
    cnx.close()
